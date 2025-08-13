"""
統一エラーハンドリングシステム
"""

import logging
import traceback
from typing import Dict, Any, Optional
from datetime import datetime

from .exceptions import *

logger = logging.getLogger(__name__)

class ErrorHandler:
    """統一エラーハンドリングクラス"""
    
    @staticmethod
    def handle_error(
        error: Exception,
        context: Dict[str, Any] = None,
        job_id: str = None,
        user_friendly: bool = True
    ) -> Dict[str, Any]:
        """エラーを統一的に処理"""
        
        context = context or {}
        error_info = {
            "timestamp": datetime.utcnow().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "job_id": job_id,
            "context": context
        }
        
        # エラー分類と適切なメッセージ生成
        if isinstance(error, VideoNotFoundError):
            error_info.update({
                "category": "video_not_found",
                "user_message": "指定された動画が見つからないか、アクセスできません。",
                "retry_recommended": False,
                "http_status": 404
            })
            
        elif isinstance(error, DownloadTimeoutError):
            error_info.update({
                "category": "timeout",
                "user_message": "ダウンロードがタイムアウトしました。しばらく時間をおいて再試行してください。",
                "retry_recommended": True,
                "http_status": 408
            })
            
        elif isinstance(error, NetworkError):
            error_info.update({
                "category": "network",
                "user_message": "ネットワークエラーが発生しました。接続を確認してください。",
                "retry_recommended": True,
                "http_status": 502
            })
            
        elif isinstance(error, StorageFullError):
            error_info.update({
                "category": "storage",
                "user_message": "サーバーのストレージ容量が不足しています。",
                "retry_recommended": False,
                "http_status": 507
            })
            
        elif isinstance(error, RateLimitExceededError):
            error_info.update({
                "category": "rate_limit",
                "user_message": "リクエスト制限に達しました。しばらく時間をおいて再試行してください。",
                "retry_recommended": True,
                "http_status": 429
            })
            
        else:
            # 未分類エラー
            error_info.update({
                "category": "unknown",
                "user_message": "予期しないエラーが発生しました。" if user_friendly else str(error),
                "retry_recommended": True,
                "http_status": 500
            })
        
        # ログ出力
        logger.error(
            f"Error handled: {error_info['category']} - {error_info['error_message']}",
            extra={
                "job_id": job_id,
                "error_info": error_info,
                "traceback": traceback.format_exc()
            }
        )
        
        return error_info
