import os
import shutil
import aiofiles
import logging
from typing import Optional, Dict, Any
from pathlib import Path
import hashlib
import mimetypes
import time

from ..core.config import settings
from ..utils.helpers import sanitize_filename

logger = logging.getLogger(__name__)

class FileService:
    """ファイル管理サービス"""
    
    def __init__(self):
        self.storage_path = Path(settings.STORAGE_PATH)
        self.storage_path.mkdir(exist_ok=True)
    
    async def get_file_info(self, filename: str) -> Optional[Dict[str, Any]]:
        """ファイル情報を取得"""
        try:
            filepath = self.storage_path / filename
            
            if not filepath.exists():
                return None
            
            stat = filepath.stat()
            mime_type, _ = mimetypes.guess_type(str(filepath))
            
            return {
                "filename": filename,
                "filesize": stat.st_size,
                "created_at": stat.st_ctime,
                "modified_at": stat.st_mtime,
                "mime_type": mime_type,
                "extension": filepath.suffix
            }
            
        except Exception as e:
            logger.error(f"ファイル情報取得エラー: {e}")
            return None
    
    async def save_file(self, filename: str, content: bytes) -> bool:
        """ファイルを保存"""
        try:
            safe_filename = sanitize_filename(filename)
            filepath = self.storage_path / safe_filename
            
            async with aiofiles.open(filepath, 'wb') as f:
                await f.write(content)
            
            logger.info(f"ファイル保存完了: {safe_filename}")
            return True
            
        except Exception as e:
            logger.error(f"ファイル保存エラー: {e}")
            return False
    
    async def delete_file(self, filename: str) -> bool:
        """ファイルを削除"""
        try:
            filepath = self.storage_path / filename
            
            if filepath.exists():
                filepath.unlink()
                logger.info(f"ファイル削除完了: {filename}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"ファイル削除エラー: {e}")
            return False
    
    async def get_storage_usage(self) -> Dict[str, Any]:
        """ストレージ使用量を取得（非同期版）"""
        try:
            total_size = 0
            file_count = 0
            
            for filepath in self.storage_path.rglob('*'):
                if filepath.is_file():
                    total_size += filepath.stat().st_size
                    file_count += 1
            
            # ディスク使用量
            disk_usage = shutil.disk_usage(self.storage_path)
            
            return {
                "total_files": file_count,
                "total_size_bytes": total_size,
                "total_size_mb": total_size / (1024 * 1024),
                "total_size_gb": total_size / (1024 * 1024 * 1024),
                "disk_total": disk_usage.total,
                "disk_used": disk_usage.used,
                "disk_free": disk_usage.free,
                "disk_usage_percent": (disk_usage.used / disk_usage.total) * 100
            }
            
        except Exception as e:
            logger.error(f"ストレージ使用量取得エラー: {e}")
            return {}
    
    def get_storage_usage_sync(self) -> Dict[str, Any]:
        """ストレージ使用量を取得（同期版）"""
        try:
            total_size = 0
            file_count = 0
            
            for filepath in self.storage_path.rglob('*'):
                if filepath.is_file():
                    total_size += filepath.stat().st_size
                    file_count += 1
            
            # ディスク使用量
            disk_usage = shutil.disk_usage(self.storage_path)
            
            return {
                "total_files": file_count,
                "total_size_bytes": total_size,
                "total_size_mb": total_size / (1024 * 1024),
                "total_size_gb": total_size / (1024 * 1024 * 1024),
                "disk_total": disk_usage.total,
                "disk_used": disk_usage.used,
                "disk_free": disk_usage.free,
                "disk_usage_percent": (disk_usage.used / disk_usage.total) * 100
            }
            
        except Exception as e:
            logger.error(f"ストレージ使用量取得エラー: {e}")
            return {}
    
    async def cleanup_old_files(self, max_age_days: int = 7) -> int:
        """古いファイルを削除（非同期版）"""
        try:
            current_time = time.time()
            cutoff_time = current_time - (max_age_days * 24 * 3600)
            
            deleted_count = 0
            
            for filepath in self.storage_path.rglob('*'):
                if filepath.is_file():
                    if filepath.stat().st_mtime < cutoff_time:
                        try:
                            filepath.unlink()
                            deleted_count += 1
                            logger.info(f"古いファイルを削除: {filepath.name}")
                        except Exception as e:
                            logger.error(f"ファイル削除失敗: {filepath.name}, {e}")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"古いファイルクリーンアップエラー: {e}")
            return 0
    
    def cleanup_old_files_sync(self, max_age_days: int = 7) -> int:
        """古いファイルを削除（同期版）"""
        try:
            current_time = time.time()
            cutoff_time = current_time - (max_age_days * 24 * 3600)
            
            deleted_count = 0
            
            for filepath in self.storage_path.rglob('*'):
                if filepath.is_file():
                    if filepath.stat().st_mtime < cutoff_time:
                        try:
                            filepath.unlink()
                            deleted_count += 1
                            logger.info(f"古いファイルを削除: {filepath.name}")
                        except Exception as e:
                            logger.error(f"ファイル削除失敗: {filepath.name}, {e}")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"古いファイルクリーンアップエラー: {e}")
            return 0
    
    def get_safe_filename(self, original_filename: str) -> str:
        """安全なファイル名を生成"""
        return sanitize_filename(original_filename)
    
    async def calculate_file_hash(self, filename: str) -> Optional[str]:
        """ファイルハッシュを計算"""
        try:
            filepath = self.storage_path / filename
            
            if not filepath.exists():
                return None
            
            hasher = hashlib.md5()
            async with aiofiles.open(filepath, 'rb') as f:
                while chunk := await f.read(8192):
                    hasher.update(chunk)
            
            return hasher.hexdigest()
            
        except Exception as e:
            logger.error(f"ファイルハッシュ計算エラー: {e}")
            return None
    
    def calculate_file_hash_sync(self, filename: str) -> Optional[str]:
        """ファイルハッシュを計算（同期版）"""
        try:
            filepath = self.storage_path / filename
            
            if not filepath.exists():
                return None
            
            hasher = hashlib.md5()
            with open(filepath, 'rb') as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            
            return hasher.hexdigest()
            
        except Exception as e:
            logger.error(f"ファイルハッシュ計算エラー: {e}")
            return None
