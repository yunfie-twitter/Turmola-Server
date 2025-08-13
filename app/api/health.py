"""
強化されたヘルスチェックシステム
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import redis
import logging
from datetime import datetime

from ..core.config import settings
from ..utils.resource_monitor import ResourceMonitor

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/health")
async def basic_health_check():
    """基本ヘルスチェック"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@router.get("/health/detailed")
async def detailed_health_check():
    """詳細ヘルスチェック"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {}
    }
    
    overall_healthy = True
    
    # Redis接続チェック
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        redis_client.ping()
        health_status["components"]["redis"] = {
            "status": "healthy"
        }
    except Exception as e:
        overall_healthy = False
        health_status["components"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # リソースチェック
    try:
        resource_check = ResourceMonitor.check_resource_limits()
        health_status["components"]["resources"] = {
            "status": resource_check["status"],
            "warnings": resource_check["warnings"],
            "critical": resource_check["critical"]
        }
        
        if resource_check["status"] == "critical":
            overall_healthy = False
    except Exception as e:
        overall_healthy = False
        health_status["components"]["resources"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Celeryワーカーチェック
    try:
        from ..core.celery_app import celery_app
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()
        
        if active_workers:
            health_status["components"]["celery"] = {
                "status": "healthy",
                "active_workers": len(active_workers),
                "workers": list(active_workers.keys())
            }
        else:
            overall_healthy = False
            health_status["components"]["celery"] = {
                "status": "unhealthy",
                "error": "No active workers found"
            }
    except Exception as e:
        overall_healthy = False
        health_status["components"]["celery"] = {
            "status": "error",
            "error": str(e)
        }
    
    health_status["status"] = "healthy" if overall_healthy else "unhealthy"
    
    if not overall_healthy:
        raise HTTPException(status_code=503, detail=health_status)
    
    return health_status

@router.get("/health/readiness")
async def readiness_probe():
    """Kubernetes readiness probe用"""
    try:
        # 基本的な依存関係チェック
        redis_client = redis.from_url(settings.REDIS_URL)
        redis_client.ping()
        
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness probe failed: {e}")
        raise HTTPException(status_code=503, detail={"status": "not_ready", "error": str(e)})

@router.get("/health/liveness")
async def liveness_probe():
    """Kubernetes liveness probe用"""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}
