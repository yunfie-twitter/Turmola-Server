from fastapi import APIRouter, Request
import logging
import platform
import psutil
import os
from datetime import datetime, timedelta

from ..models.server import ServerInfo
from ..utils.rate_limiter import smart_rate_limit
from ..core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/server-info", response_model=ServerInfo)
@smart_rate_limit("60/minute")
async def get_server_info(request: Request):
    """サーバー情報を取得"""
    
    try:
        # システム情報取得
        system_info = {
            "os_version": f"{platform.system()} {platform.release()}",
            "python_version": platform.python_version(),
        }
        
        # yt-dlpバージョン取得
        try:
            import yt_dlp
            yt_dlp_version = yt_dlp.version.__version__
        except:
            yt_dlp_version = "Unknown"
        
        # プロセス情報
        process = psutil.Process()
        uptime_seconds = datetime.now().timestamp() - process.create_time()
        
        # メモリ使用量
        memory_info = psutil.virtual_memory()
        memory_usage = {
            "used": memory_info.used // (1024 * 1024),  # MB
            "available": memory_info.available // (1024 * 1024),  # MB
            "percent": memory_info.percent
        }
        
        # ディスク使用量
        disk_info = psutil.disk_usage(settings.STORAGE_PATH)
        disk_usage = {
            "used": disk_info.used // (1024 * 1024 * 1024),  # GB
            "free": disk_info.free // (1024 * 1024 * 1024),   # GB
            "percent": (disk_info.used / disk_info.total) * 100
        }
        
        # Celeryワーカー情報取得
        try:
            from ..core.celery_app import celery_app
            inspect = celery_app.control.inspect()
            
            # アクティブタスク
            active_tasks = inspect.active() or {}
            running_jobs = sum(len(tasks) for tasks in active_tasks.values())
            
            # 予約済みタスク
            reserved_tasks = inspect.reserved() or {}
            pending_jobs = sum(len(tasks) for tasks in reserved_tasks.values())
            
        except Exception as e:
            logger.warning(f"Celery情報取得エラー: {e}")
            running_jobs = 0
            pending_jobs = 0
        
        # サーバー種別判定（プレミアム機能の有無で判定）
        server_type = "Premium" if hasattr(settings, 'PREMIUM_API_KEY') else "Normal"
        max_concurrent = (settings.MAX_CONCURRENT_JOBS_PREMIUM 
                         if server_type == "Premium" 
                         else settings.MAX_CONCURRENT_JOBS_NORMAL)
        
        return ServerInfo(
            server_type=server_type,
            yt_dlp_version=yt_dlp_version,
            os_version=system_info["os_version"],
            python_version=system_info["python_version"],
            pending_jobs=pending_jobs,
            running_jobs=running_jobs,
            max_concurrent_jobs=max_concurrent,
            uptime=uptime_seconds,
            memory_usage=memory_usage,
            disk_usage=disk_usage
        )
        
    except Exception as e:
        logger.error(f"サーバー情報取得エラー: {e}")
        # エラー時のデフォルト値
        return ServerInfo(
            server_type="Unknown",
            yt_dlp_version="Unknown",
            os_version="Unknown",
            python_version=platform.python_version(),
            pending_jobs=0,
            running_jobs=0,
            max_concurrent_jobs=3,
            uptime=0,
            memory_usage={"used": 0, "available": 0, "percent": 0},
            disk_usage={"used": 0, "free": 0, "percent": 0}
        )

@router.get("/server-status")
@smart_rate_limit("30/minute")
async def get_server_status(request: Request):
    """簡単なサーバー状態確認"""
    
    try:
        # Redis接続確認
        from ..core.redis_client import redis_client
        redis_status = "connected"
        try:
            await redis_client.ping()
        except Exception:
            redis_status = "disconnected"
        
        # Celery接続確認
        celery_status = "connected"
        try:
            from ..core.celery_app import celery_app
            inspect = celery_app.control.inspect()
            stats = inspect.stats()
            if not stats:
                celery_status = "no_workers"
        except Exception:
            celery_status = "disconnected"
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "redis": redis_status,
                "celery": celery_status,
                "api": "running"
            },
            "rate_limiting": settings.ENABLE_RATE_LIMITING if hasattr(settings, 'ENABLE_RATE_LIMITING') else False
        }
        
    except Exception as e:
        logger.error(f"サーバー状態確認エラー: {e}")
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }
