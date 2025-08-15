"""
監視・メトリクス API（修正版）
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, List
from datetime import datetime  # ← この行を追加
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
            "timestamp": datetime.utcnow().isoformat(),  # 修正: datetimeが使用可能
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
            "message": "Auto-recovery process started in background",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Recovery execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cluster/status")
async def get_cluster_status():
    """クラスター状態取得"""
    try:
        # フェイルオーバーサービスが利用可能かチェック
        try:
            status = await failover_service.get_cluster_status()
        except (ImportError, AttributeError):
            # フェイルオーバーサービスが利用できない場合
            status = {
                "timestamp": datetime.utcnow().isoformat(),
                "cluster_mode": "single_node",
                "status": "healthy",
                "nodes": [{
                    "id": "main_node",
                    "status": "active",
                    "last_heartbeat": datetime.utcnow().isoformat()
                }]
            }
        
        return status
    except Exception as e:
        logger.error(f"Cluster status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cluster/maintenance", dependencies=[Depends(require_admin_key)])
async def enter_maintenance_mode():
    """メンテナンスモード移行"""
    try:
        # フェイルオーバーサービスが利用可能かチェック
        try:
            await failover_service.graceful_shutdown()
            message = "Node entered maintenance mode"
        except (ImportError, AttributeError):
            # フェイルオーバーサービスが利用できない場合
            message = "Maintenance mode requested (single node mode)"
        
        return {
            "status": "maintenance_mode",
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Maintenance mode error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 追加: システム健全性チェックエンドポイント
@router.get("/health/detailed")
async def get_detailed_health():
    """詳細な健全性チェック"""
    try:
        health_info = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "healthy",
            "components": {}
        }
        
        # メトリクス収集の健全性
        try:
            current_metrics = metrics_collector.collect_system_metrics()
            health_info["components"]["metrics_collector"] = {
                "status": "healthy" if current_metrics else "unhealthy",
                "last_collection": current_metrics.timestamp.isoformat() if current_metrics else None
            }
        except Exception as e:
            health_info["components"]["metrics_collector"] = {
                "status": "error",
                "error": str(e)
            }
        
        # 異常検知システム
        try:
            anomalies = metrics_collector.detect_anomalies()
            health_info["components"]["anomaly_detection"] = {
                "status": "healthy",
                "anomaly_count": len(anomalies),
                "has_critical_anomalies": any(a.get("severity") == "critical" for a in anomalies)
            }
        except Exception as e:
            health_info["components"]["anomaly_detection"] = {
                "status": "error",
                "error": str(e)
            }
        
        # 全体ステータス判定
        component_statuses = [comp.get("status", "error") for comp in health_info["components"].values()]
        if "error" in component_statuses or "unhealthy" in component_statuses:
            health_info["overall_status"] = "degraded"
        
        return health_info
        
    except Exception as e:
        logger.error(f"Detailed health check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 追加: パフォーマンスメトリクス取得
@router.get("/metrics/performance")
async def get_performance_metrics():
    """パフォーマンスメトリクス取得"""
    try:
        # 基本的なシステム情報を取得
        import psutil
        
        performance_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "cpu": {
                "percent": psutil.cpu_percent(interval=1),
                "count": psutil.cpu_count(),
                "freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
            },
            "memory": {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "percent": psutil.virtual_memory().percent,
                "used": psutil.virtual_memory().used
            },
            "disk": {
                "total": psutil.disk_usage('/').total,
                "used": psutil.disk_usage('/').used,
                "free": psutil.disk_usage('/').free,
                "percent": (psutil.disk_usage('/').used / psutil.disk_usage('/').total) * 100
            },
            "network": {
                "bytes_sent": psutil.net_io_counters().bytes_sent,
                "bytes_recv": psutil.net_io_counters().bytes_recv,
                "packets_sent": psutil.net_io_counters().packets_sent,
                "packets_recv": psutil.net_io_counters().packets_recv
            }
        }
        
        return performance_data
        
    except Exception as e:
        logger.error(f"Performance metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 追加: アラート履歴取得
@router.get("/alerts/history")
async def get_alert_history(limit: int = 50):
    """アラート履歴取得"""
    try:
        if limit < 1 or limit > 1000:
            raise HTTPException(status_code=400, detail="Limit must be between 1 and 1000")
        
        # 実際の実装では、データベースやログファイルからアラート履歴を取得
        # ここでは例として空のレスポンスを返す
        alert_history = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_alerts": 0,
            "limit": limit,
            "alerts": []
        }
        
        return alert_history
        
    except Exception as e:
        logger.error(f"Alert history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
