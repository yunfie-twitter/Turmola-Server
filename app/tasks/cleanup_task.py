import logging
import asyncio
from datetime import datetime

from ..core.celery_app import celery_app
from ..core.config import settings
from ..services.file_service import FileService

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def cleanup_old_files(self):
    """古いファイルを削除する定期タスク"""
    
    try:
        logger.info("ファイルクリーンアップ開始")
        
        # 非同期関数を同期的に実行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            file_service = FileService()
            
            # ストレージ使用量確認
            usage = loop.run_until_complete(file_service.get_storage_usage())
            logger.info(f"現在のストレージ使用量: {usage.get('total_size_gb', 0):.2f} GB")
            
            # 古いファイル削除
            deleted_count = loop.run_until_complete(
                file_service.cleanup_old_files(max_age_days=settings.MAX_FILE_AGE_DAYS)
            )
            
            logger.info(f"ファイルクリーンアップ完了: {deleted_count}個のファイルを削除")
            
            return {
                "deleted_files": deleted_count,
                "storage_usage": usage,
                "completed_at": datetime.utcnow().isoformat()
            }
            
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"ファイルクリーンアップエラー: {e}")
        raise

@celery_app.task(bind=True)
def monitor_storage_usage(self):
    """ストレージ使用量監視タスク"""
    
    try:
        # 非同期関数を同期的に実行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            file_service = FileService()
            usage = loop.run_until_complete(file_service.get_storage_usage())
            
            usage_gb = usage.get('total_size_gb', 0)
            usage_percent = usage.get('disk_usage_percent', 0)
            
            # 警告レベル確認
            if usage_gb > settings.MAX_STORAGE_GB:
                logger.warning(f"ストレージ使用量が上限を超過: {usage_gb:.2f} GB > {settings.MAX_STORAGE_GB} GB")
                
                # 緊急クリーンアップ
                deleted_count = loop.run_until_complete(
                    file_service.cleanup_old_files(max_age_days=3)
                )
                logger.info(f"緊急クリーンアップ実行: {deleted_count}個のファイルを削除")
            
            elif usage_percent > 80:
                logger.warning(f"ディスク使用量が80%を超過: {usage_percent:.1f}%")
            
            return {
                "storage_usage_gb": usage_gb,
                "disk_usage_percent": usage_percent,
                "warning_triggered": usage_gb > settings.MAX_STORAGE_GB,
                "checked_at": datetime.utcnow().isoformat()
            }
            
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"ストレージ監視エラー: {e}")
        raise

# 同期版のヘルパー関数も追加
def run_async_task(coro):
    """非同期タスクを同期的に実行するヘルパー関数"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)

# より簡潔な書き方の代替案
@celery_app.task(bind=True)
def cleanup_old_files_v2(self):
    """古いファイルを削除する定期タスク（簡潔版）"""
    
    async def _cleanup():
        file_service = FileService()
        usage = await file_service.get_storage_usage()
        deleted_count = await file_service.cleanup_old_files(
            max_age_days=settings.MAX_FILE_AGE_DAYS
        )
        return {"deleted_files": deleted_count, "storage_usage": usage}
    
    try:
        logger.info("ファイルクリーンアップ開始")
        result = run_async_task(_cleanup())
        logger.info(f"ファイルクリーンアップ完了: {result['deleted_files']}個のファイルを削除")
        
        result["completed_at"] = datetime.utcnow().isoformat()
        return result
        
    except Exception as e:
        logger.error(f"ファイルクリーンアップエラー: {e}")
        raise
