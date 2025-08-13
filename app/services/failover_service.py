"""
フェイルオーバー・高可用性サービス
"""

import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum
import redis

from ..core.config import settings
from ..services.auto_recovery import AutoRecoverySystem

logger = logging.getLogger(__name__)

class NodeStatus(Enum):
    ACTIVE = "active"
    STANDBY = "standby"  
    DOWN = "down"
    MAINTENANCE = "maintenance"

class FailoverService:
    """フェイルオーバー管理サービス"""
    
    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.node_id = settings.NODE_ID if hasattr(settings, 'NODE_ID') else "node-1"
        self.heartbeat_interval = 30  # 30秒
        self.failover_timeout = 120   # 2分
        
    async def start_heartbeat(self):
        """ハートビート開始"""
        while True:
            try:
                await self._send_heartbeat()
                await self._check_other_nodes()
                await asyncio.sleep(self.heartbeat_interval)
                
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(5)
    
    async def _send_heartbeat(self):
        """ハートビート送信"""
        try:
            heartbeat_data = {
                "node_id": self.node_id,
                "timestamp": datetime.utcnow().isoformat(),
                "status": NodeStatus.ACTIVE.value,
                "load": await self._get_node_load(),
                "active_jobs": await self._get_active_jobs_count()
            }
            
            # Redis に保存（TTL付き）
            key = f"heartbeat:{self.node_id}"
            self.redis_client.setex(
                key,
                self.heartbeat_interval * 2,  # TTLはハートビート間隔の2倍
                json.dumps(heartbeat_data)
            )
            
            logger.debug(f"Heartbeat sent: {self.node_id}")
            
        except Exception as e:
            logger.error(f"Heartbeat send error: {e}")
    
    async def _check_other_nodes(self):
        """他ノードの状態確認"""
        try:
            # 全ハートビートキー取得
            keys = self.redis_client.keys("heartbeat:*")
            active_nodes = []
            down_nodes = []
            
            for key in keys:
                try:
                    data = self.redis_client.get(key)
                    if data:
                        heartbeat = json.loads(data)
                        node_id = heartbeat["node_id"]
                        timestamp = datetime.fromisoformat(heartbeat["timestamp"])
                        
                        # ハートビートの新鮮さチェック
                        age = (datetime.utcnow() - timestamp).total_seconds()
                        
                        if age < self.failover_timeout:
                            active_nodes.append(heartbeat)
                        else:
                            down_nodes.append(node_id)
                            
                except Exception as e:
                    logger.warning(f"Heartbeat parse error for {key}: {e}")
            
            # ダウンノード検出時の処理
            if down_nodes:
                await self._handle_node_failures(down_nodes)
            
            # クラスター状態更新
            await self._update_cluster_status(active_nodes, down_nodes)
            
        except Exception as e:
            logger.error(f"Node check error: {e}")
    
    async def _handle_node_failures(self, down_nodes: List[str]):
        """ノード障害処理"""
        logger.warning(f"Detected down nodes: {down_nodes}")
        
        for node_id in down_nodes:
            try:
                # ダウンノードのジョブを他ノードに移行
                await self._migrate_jobs_from_node(node_id)
                
                # ダウンノードの情報をクリーンアップ
                self.redis_client.delete(f"heartbeat:{node_id}")
                
                logger.info(f"Handled failure for node: {node_id}")
                
            except Exception as e:
                logger.error(f"Node failure handling error for {node_id}: {e}")
    
    async def _migrate_jobs_from_node(self, failed_node_id: str):
        """失敗ノードからのジョブ移行"""
        try:
            # 失敗ノードで実行中のジョブを検索
            running_jobs_key = f"running_jobs:{failed_node_id}"
            running_jobs = self.redis_client.smembers(running_jobs_key)
            
            migrated_count = 0
            
            for job_id in running_jobs:
                try:
                    # ジョブを他ノードで再実行
                    job_data = self.redis_client.get(f"job:{job_id}")
                    if job_data:
                        job_info = json.loads(job_data)
                        
                        # ジョブのステータスを「pending」に戻す
                        job_info["status"] = "pending"
                        job_info["node_id"] = None
                        job_info["migration_note"] = f"Migrated from failed node: {failed_node_id}"
                        
                        self.redis_client.set(
                            f"job:{job_id}",
                            json.dumps(job_info),
                            ex=86400
                        )
                        
                        # Celeryキューに再投入
                        from ..tasks.download_task import download_video
                        download_video.apply_async(
                            args=[job_id, job_info["url"], job_info["options"]]
                        )
                        
                        migrated_count += 1
                        logger.info(f"Migrated job {job_id} from failed node {failed_node_id}")
                        
                except Exception as e:
                    logger.error(f"Job migration error for {job_id}: {e}")
            
            # 失敗ノードの実行中ジョブリストをクリア
            self.redis_client.delete(running_jobs_key)
            
            logger.info(f"Migrated {migrated_count} jobs from failed node: {failed_node_id}")
            
        except Exception as e:
            logger.error(f"Job migration error: {e}")
    
    async def _update_cluster_status(self, active_nodes: List[Dict], down_nodes: List[str]):
        """クラスター状態更新"""
        try:
            cluster_status = {
                "timestamp": datetime.utcnow().isoformat(),
                "active_nodes": len(active_nodes),
                "down_nodes": len(down_nodes),
                "total_nodes": len(active_nodes) + len(down_nodes),
                "nodes": {
                    "active": active_nodes,
                    "down": down_nodes
                }
            }
            
            # クラスター状態をRedisに保存
            self.redis_client.setex(
                "cluster:status",
                300,  # 5分間有効
                json.dumps(cluster_status)
            )
            
        except Exception as e:
            logger.error(f"Cluster status update error: {e}")
    
    async def _get_node_load(self) -> float:
        """ノード負荷取得"""
        try:
            import psutil
            return psutil.cpu_percent(interval=0.1)
        except:
            return 0.0
    
    async def _get_active_jobs_count(self) -> int:
        """アクティブジョブ数取得"""
        try:
            # 簡易実装：実際にはCeleryから取得
            return len(self.redis_client.keys("job:*"))
        except:
            return 0
    
    async def get_cluster_status(self) -> Dict[str, Any]:
        """クラスター状態取得"""
        try:
            status_data = self.redis_client.get("cluster:status")
            if status_data:
                return json.loads(status_data)
            else:
                return {
                    "error": "Cluster status not available",
                    "timestamp": datetime.utcnow().isoformat()
                }
        except Exception as e:
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def graceful_shutdown(self):
        """グレースフルシャットダウン"""
        try:
            # 自ノードをメンテナンスモードに変更
            heartbeat_data = {
                "node_id": self.node_id,
                "timestamp": datetime.utcnow().isoformat(),
                "status": NodeStatus.MAINTENANCE.value,
                "shutdown_initiated": True
            }
            
            key = f"heartbeat:{self.node_id}"
            self.redis_client.setex(key, 300, json.dumps(heartbeat_data))
            
            # 実行中ジョブの完了を待つ
            await self._wait_for_jobs_completion()
            
            # ハートビート停止
            self.redis_client.delete(key)
            
            logger.info("Graceful shutdown completed")
            
        except Exception as e:
            logger.error(f"Graceful shutdown error: {e}")
    
    async def _wait_for_jobs_completion(self, timeout: int = 300):
        """実行中ジョブの完了待ち"""
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            try:
                active_jobs = await self._get_active_jobs_count()
                if active_jobs == 0:
                    logger.info("All jobs completed, safe to shutdown")
                    return
                
                logger.info(f"Waiting for {active_jobs} jobs to complete...")
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Job completion check error: {e}")
                break
        
        logger.warning("Shutdown timeout reached, forcing shutdown")

# グローバルフェイルオーバーサービス
failover_service = FailoverService()
