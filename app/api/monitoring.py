"""
監視・メトリクス API
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, List
import logging

from ..services.metrics_collector import metrics_collector
from ..services.auto_recovery import AutoRecoverySystem
from ..services.failover_service import failover_service
from ..middleware.security import require_admin_key

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/metrics/current")
async def get_current_metrics():
    """現在のシステムメトリクス取得"""
    try:
        snapshot = metrics_collector.collect_system_metrics()
        if snapshot:
            return {
                "timestamp": snapshot.timestamp.isoformat(),
                "cpu_percent": snapshot.cpu_percent,
                "memory_percent": snapshot.memory_percent,
                "disk_percent": snapshot.disk_percent,
                "active_jobs": snapshot.active_jobs,
                "pending_jobs": snapshot.pending_jobs,
                "failed_jobs_last_hour": snapshot.failed_jobs_last_hour,
                "response_time_avg": snapshot.response_time_avg
            }
        else:
            raise HTTPException(status_code=500, detail="Metrics collection failed")
    except Exception as e:
        logger.error(f"Current metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics/summary")
async def get_metrics_summary(hours: int = 24):
    """メトリクス集計サマリー取得"""
    if hours < 1 or hours > 168:  # 1時間〜7日間
        raise HTTPException(status_code=400, detail="Hours must be between 1 and 168")
    
    try:
        summary = metrics_collector.get_metrics_summary(hours)
        return summary
    except Exception as e:
        logger.error(f"Metrics summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics/anomalies")
async def get_anomalies():
    """異常検知結果取得"""
    try:
        anomalies = metrics_collector.detect_anomalies()
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "anomaly_count": len(anomalies),
            "anomalies": anomalies
        }
    except Exception as e:
        logger.error(f"Anomaly detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/recovery/execute", dependencies=[Depends(require_admin_key)])
async def execute_recovery(background_tasks: BackgroundTasks):
    """手動回復処理実行"""
    try:
        recovery_system = AutoRecoverySystem()
        
        # バックグラウンドで回復処理を実行
        background_tasks.add_task(recovery_system.perform_health_checks)
        
        return {
            "status": "recovery_initiated",
            "message": "Auto-recovery process started in background"
        }
    except Exception as e:
        logger.error(f"Recovery execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cluster/status")
async def get_cluster_status():
    """クラスター状態取得"""
    try:
        status = await failover_service.get_cluster_status()
        return status
    except Exception as e:
        logger.error(f"Cluster status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cluster/maintenance", dependencies=[Depends(require_admin_key)])
async def enter_maintenance_mode():
    """メンテナンスモード移行"""
    try:
        await failover_service.graceful_shutdown()
        return {
            "status": "maintenance_mode",
            "message": "Node entered maintenance mode"
        }
    except Exception as e:
        logger.error(f"Maintenance mode error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
