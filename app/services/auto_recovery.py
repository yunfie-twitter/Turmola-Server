"""
自動回復システム
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
import psutil
import redis
from celery import Celery

from ..core.config import settings
from ..core.celery_app import celery_app
from ..services.job_persistence import JobPersistenceService
from ..utils.resource_monitor import ResourceMonitor

logger = logging.getLogger(__name__)

class AutoRecoverySystem:
    """自動回復システム"""
    
    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.job_service = JobPersistenceService()
        
    async def perform_health_checks(self) -> Dict[str, Any]:
        """包括的ヘルスチェック実行"""
        health_status = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "healthy",
            "components": {},
            "recovery_actions": []
        }
        
        # Redis接続チェック
        redis_status = await self._check_redis_health()
        health_status["components"]["redis"] = redis_status
        
        if redis_status["status"] != "healthy":
            recovery_action = await self._recover_redis()
            health_status["recovery_actions"].append(recovery_action)
        
        # Celeryワーカーチェック
        celery_status = await self._check_celery_health()
        health_status["components"]["celery"] = celery_status
        
        if celery_status["status"] != "healthy":
            recovery_action = await self._recover_celery_workers()
            health_status["recovery_actions"].append(recovery_action)
        
        # リソースチェック
        resource_status = await self._check_resource_health()
        health_status["components"]["resources"] = resource_status
        
        if resource_status["status"] == "critical":
            recovery_action = await self._recover_resources()
            health_status["recovery_actions"].append(recovery_action)
        
        # 失敗ジョブの自動リトライ
        retry_action = await self._retry_failed_jobs()
        if retry_action["retried_count"] > 0:
            health_status["recovery_actions"].append(retry_action)
        
        # 全体ステータス判定
        if any(comp["status"] == "critical" for comp in health_status["components"].values()):
            health_status["overall_status"] = "critical"
        elif any(comp["status"] == "warning" for comp in health_status["components"].values()):
            health_status["overall_status"] = "warning"
        
        return health_status
    
    async def _check_redis_health(self) -> Dict[str, Any]:
        """Redis健全性チェック"""
        try:
            # 接続テスト
            response_time_start = datetime.utcnow()
            self.redis_client.ping()
            response_time = (datetime.utcnow() - response_time_start).total_seconds() * 1000
            
            # メモリ使用量チェック
            info = self.redis_client.info('memory')
            memory_usage = info.get('used_memory', 0)
            max_memory = info.get('maxmemory', 0)
            
            if max_memory > 0:
                memory_percent = (memory_usage / max_memory) * 100
            else:
                memory_percent = 0
            
            # 接続数チェック
            client_info = self.redis_client.info('clients')
            connected_clients = client_info.get('connected_clients', 0)
            
            status = "healthy"
            warnings = []
            
            if response_time > 100:  # 100ms以上
                warnings.append(f"High response time: {response_time:.1f}ms")
                status = "warning"
            
            if memory_percent > 90:
                warnings.append(f"High memory usage: {memory_percent:.1f}%")
                status = "critical"
            elif memory_percent > 80:
                warnings.append(f"Memory usage warning: {memory_percent:.1f}%")
                status = "warning"
            
            if connected_clients > 100:
                warnings.append(f"High connection count: {connected_clients}")
                status = "warning"
            
            return {
                "status": status,
                "response_time_ms": response_time,
                "memory_usage_percent": memory_percent,
                "connected_clients": connected_clients,
                "warnings": warnings
            }
            
        except Exception as e:
            return {
                "status": "critical",
                "error": str(e),
                "warnings": ["Redis connection failed"]
            }
    
    async def _check_celery_health(self) -> Dict[str, Any]:
        """Celery健全性チェック"""
        try:
            inspect = celery_app.control.inspect()
            
            # アクティブワーカー
            active_workers = inspect.active() or {}
            stats = inspect.stats() or {}
            
            total_workers = len(stats)
            total_active_tasks = sum(len(tasks) for tasks in active_workers.values())
            
            # キューの長さ
            try:
                pending_jobs = self.redis_client.llen("celery")
            except:
                pending_jobs = 0
            
            status = "healthy"
            warnings = []
            
            if total_workers == 0:
                status = "critical"
                warnings.append("No active workers")
            elif total_workers < 2:
                status = "warning"
                warnings.append(f"Low worker count: {total_workers}")
            
            if pending_jobs > 100:
                status = "warning"
                warnings.append(f"High queue backlog: {pending_jobs}")
            
            return {
                "status": status,
                "active_workers": total_workers,
                "active_tasks": total_active_tasks,
                "pending_jobs": pending_jobs,
                "warnings": warnings
            }
            
        except Exception as e:
            return {
                "status": "critical",
                "error": str(e),
                "warnings": ["Celery inspection failed"]
            }
    
    async def _check_resource_health(self) -> Dict[str, Any]:
        """システムリソース健全性チェック"""
        try:
            resource_check = ResourceMonitor.check_resource_limits()
            return resource_check
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "warnings": ["Resource monitoring failed"]
            }
    
    async def _recover_redis(self) -> Dict[str, Any]:
        """Redis回復処理"""
        try:
            # メモリクリーンアップ
            self.redis_client.flushdb()  # 開発環境のみ推奨
            
            # 接続プールリセット
            self.redis_client.connection_pool.disconnect()
            
            return {
                "action": "redis_recovery",
                "status": "completed",
                "details": "Redis memory cleared and connections reset"
            }
            
        except Exception as e:
            return {
                "action": "redis_recovery",
                "status": "failed",
                "error": str(e)
            }
    
    async def _recover_celery_workers(self) -> Dict[str, Any]:
        """Celeryワーカー回復処理"""
        try:
            # 応答しないワーカーを検出して再起動要求
            control = celery_app.control
            
            # ワーカーにping送信
            ping_responses = control.ping(timeout=10)
            
            if not ping_responses:
                # ワーカーが応答しない場合のログ記録
                logger.warning("No Celery workers responding to ping")
                
                return {
                    "action": "celery_recovery",
                    "status": "requires_manual_restart",
                    "details": "No workers responding, manual restart required"
                }
            
            return {
                "action": "celery_recovery",
                "status": "healthy",
                "details": f"Workers responding: {len(ping_responses)}"
            }
            
        except Exception as e:
            return {
                "action": "celery_recovery",
                "status": "failed",
                "error": str(e)
            }
    
    async def _recover_resources(self) -> Dict[str, Any]:
        """リソース回復処理"""
        try:
            recovery_actions = []
            
            # メモリクリーンアップ
            try:
                import gc
                gc.collect()
                recovery_actions.append("garbage_collection")
            except:
                pass
            
            # 古いファイルの削除
            try:
                from ..tasks.cleanup_task import cleanup_old_files
                cleanup_old_files.delay()
                recovery_actions.append("file_cleanup_scheduled")
            except:
                pass
            
            return {
                "action": "resource_recovery",
                "status": "completed",
                "details": f"Actions taken: {', '.join(recovery_actions)}"
            }
            
        except Exception as e:
            return {
                "action": "resource_recovery",
                "status": "failed",
                "error": str(e)
            }
    
    async def _retry_failed_jobs(self) -> Dict[str, Any]:
        """失敗ジョブの自動リトライ"""
        try:
            failed_jobs = self.job_service.get_failed_jobs_for_retry()
            retried_count = 0
            
            for job in failed_jobs:
                try:
                    # リトライ処理
                    from ..tasks.download_task import download_video
                    download_video.apply_async(
                        args=[job.job_id, job.url, job.options],
                        countdown=60 * (job.retry_count + 1)  # 指数バックオフ
                    )
                    
                    # リトライカウント更新
                    job.retry_count += 1
                    self.job_service.update_job_status(
                        job.job_id,
                        "retrying",
                        error_message=f"Auto-retry #{job.retry_count}"
                    )
                    
                    retried_count += 1
                    logger.info(f"Auto-retry scheduled: {job.job_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to retry job {job.job_id}: {e}")
            
            return {
                "action": "failed_job_retry",
                "status": "completed",
                "retried_count": retried_count,
                "details": f"Retried {retried_count} failed jobs"
            }
            
        except Exception as e:
            return {
                "action": "failed_job_retry",
                "status": "failed",
                "error": str(e),
                "retried_count": 0
            }

# 定期実行用のヘルスチェック関数
async def scheduled_health_check():
    """定期ヘルスチェック（Celery Beatから呼び出し）"""
    recovery_system = AutoRecoverySystem()
    health_report = await recovery_system.perform_health_checks()
    
    # 重要な問題があればアラート
    if health_report["overall_status"] == "critical":
        logger.critical(f"System critical status detected: {health_report}")
        # ここで外部アラート送信（Slack、メール等）
    
    return health_report
