"""
高度な機能 API（aria2統合・監視強化）
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, List, Optional
import logging

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
        import uuid
        
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
