from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import uuid

# 必要なインポートを追加
from ..core.config import settings
from ..services.aria2_service import aria2_service
from ..services.advanced_monitoring import advanced_monitoring
from ..middleware.security import require_premium_key

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/aria2/status")
async def get_aria2_status():
    """aria2 ステータス取得"""
    try:
        if not getattr(settings, 'ENABLE_ARIA2', False):
            return {"enabled": False, "message": "aria2 is disabled"}
        
        is_running = await aria2_service.check_aria2_status()
        stats = await aria2_service.get_global_stats() if is_running else {}
        
        return {
            "enabled": True,
            "running": is_running,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"aria2 status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/aria2/restart", dependencies=[Depends(require_premium_key)])
async def restart_aria2():
    """aria2 再起動"""
    try:
        success = await aria2_service.start_aria2_daemon()
        
        return {
            "status": "success" if success else "failed",
            "message": "aria2 restart completed" if success else "aria2 restart failed"
        }
        
    except Exception as e:
        logger.error(f"aria2 restart error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/download/enhanced", dependencies=[Depends(require_premium_key)])
async def enhanced_download(
    url: str,
    quality: str = "best",
    force_aria2: bool = False,
    aria2_connections: int = 10,
    aria2_splits: int = 10
):
    """強化ダウンロード（aria2オプション付き）"""
    try:
        options = {
            "quality": quality,
            "force_aria2": force_aria2,
            "aria2_connections": aria2_connections,
            "aria2_splits": aria2_splits
        }
        
        # 通常のダウンロードタスクを拡張オプション付きで実行
        from ..tasks.download_task import download_video
        
        job_id = str(uuid.uuid4())
        task = download_video.apply_async(args=[job_id, url, options])
        
        return {
            "job_id": job_id,
            "task_id": task.id,
            "status": "pending",
            "enhanced_options": options,
            "message": "Enhanced download started"
        }
        
    except Exception as e:
        logger.error(f"Enhanced download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/monitoring/alerts/recent")
async def get_recent_alerts(hours: int = 24):
    """最近のアラート取得"""
    try:
        alerts = advanced_monitoring.get_recent_alerts(hours)
        
        return {
            "period_hours": hours,
            "alert_count": len(alerts),
            "alerts": alerts
        }
        
    except Exception as e:
        logger.error(f"Recent alerts error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/monitoring/health/detailed")
async def get_detailed_health():
    """詳細ヘルス情報取得"""
    try:
        # アクティブアラート
        active_alerts = advanced_monitoring.get_recent_alerts(1)  # 過去1時間
        
        # システム統計
        from ..utils.resource_monitor import ResourceMonitor
        system_stats = ResourceMonitor.get_system_stats()
        
        # aria2統計（有効な場合）
        aria2_stats = {}
        if getattr(settings, 'ENABLE_ARIA2', False):
            aria2_running = await aria2_service.check_aria2_status()
            if aria2_running:
                aria2_stats = await aria2_service.get_global_stats()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "active_alerts": {
                "count": len(active_alerts),
                "critical_count": len([a for a in active_alerts if a.get('severity') == 'critical']),
                "warning_count": len([a for a in active_alerts if a.get('severity') == 'warning'])
            },
            "system_stats": system_stats,
            "aria2_stats": aria2_stats,
            "features": {
                "aria2_enabled": getattr(settings, 'ENABLE_ARIA2', False),
                "monitoring_enabled": getattr(settings, 'ENABLE_PERFORMANCE_MONITORING', False)
            }
        }
        
    except Exception as e:
        logger.error(f"Detailed health error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 追加: サービスの健全性をチェックする汎用エンドポイント
@router.get("/service/status")
async def get_service_status():
    """サービス全体のステータス取得"""
    try:
        services_status = {
            "timestamp": datetime.utcnow().isoformat(),
            "services": {}
        }
        
        # aria2 サービス
        if getattr(settings, 'ENABLE_ARIA2', False):
            try:
                aria2_running = await aria2_service.check_aria2_status()
                services_status["services"]["aria2"] = {
                    "enabled": True,
                    "running": aria2_running,
                    "status": "healthy" if aria2_running else "unhealthy"
                }
            except Exception as e:
                services_status["services"]["aria2"] = {
                    "enabled": True,
                    "running": False,
                    "status": "error",
                    "error": str(e)
                }
        else:
            services_status["services"]["aria2"] = {
                "enabled": False,
                "status": "disabled"
            }
        
        # Redis サービス
        try:
            import redis
            redis_client = redis.from_url(settings.REDIS_URL)
            redis_client.ping()
            services_status["services"]["redis"] = {
                "status": "healthy"
            }
        except Exception as e:
            services_status["services"]["redis"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Celery ワーカー
        try:
            from ..core.celery_app import celery_app
            inspect = celery_app.control.inspect()
            stats = inspect.stats() or {}
            worker_count = len(stats)
            
            services_status["services"]["celery"] = {
                "status": "healthy" if worker_count > 0 else "unhealthy",
                "active_workers": worker_count,
                "workers": list(stats.keys()) if stats else []
            }
        except Exception as e:
            services_status["services"]["celery"] = {
                "status": "error",
                "error": str(e)
            }
        
        # 全体ステータス判定
        all_services = services_status["services"]
        unhealthy_services = [
            name for name, service in all_services.items() 
            if service.get("status") in ["unhealthy", "error"] and service.get("enabled", True)
        ]
        
        services_status["overall_status"] = "unhealthy" if unhealthy_services else "healthy"
        services_status["unhealthy_services"] = unhealthy_services
        
        return services_status
        
    except Exception as e:
        logger.error(f"Service status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 追加: 設定情報取得エンドポイント
@router.get("/config/info", dependencies=[Depends(require_premium_key)])
async def get_config_info():
    """設定情報取得（管理者用）"""
    try:
        config_info = {
            "timestamp": datetime.utcnow().isoformat(),
            "environment": getattr(settings, 'ENVIRONMENT', 'unknown'),
            "features": {
                "aria2_enabled": getattr(settings, 'ENABLE_ARIA2', False),
                "rate_limiting_enabled": getattr(settings, 'ENABLE_RATE_LIMITING', False),
                "monitoring_enabled": getattr(settings, 'ENABLE_PERFORMANCE_MONITORING', False)
            },
            "limits": {
                "max_concurrent_jobs_premium": getattr(settings, 'MAX_CONCURRENT_JOBS_PREMIUM', 10),
                "max_concurrent_jobs_normal": getattr(settings, 'MAX_CONCURRENT_JOBS_NORMAL', 3),
                "aria2_threshold_mb": getattr(settings, 'ARIA2_THRESHOLD_MB', 50),
                "cache_ttl": getattr(settings, 'CACHE_TTL', 3600)
            },
            "paths": {
                "storage_path": getattr(settings, 'STORAGE_PATH', '/app/downloads'),
                "log_file": getattr(settings, 'LOG_FILE', '/app/logs/app.log')
            }
        }
        
        return config_info
        
    except Exception as e:
        logger.error(f"Config info error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
