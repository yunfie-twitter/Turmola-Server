"""
強化されたロギング設定
"""

import logging
import logging.handlers
import json
from datetime import datetime
from typing import Dict, Any

from ..core.config import settings

class JsonFormatter(logging.Formatter):
    """JSON形式のログフォーマッター"""
    
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # 追加属性があれば含める
        if hasattr(record, 'job_id'):
            log_entry['job_id'] = record.job_id
        
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        
        if hasattr(record, 'error_info'):
            log_entry['error_info'] = record.error_info
        
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        
        # 例外情報
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)

def setup_logging():
    """ロギング設定のセットアップ"""
    
    # ルートロガー設定
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))
    
    # 既存のハンドラーをクリア
    root_logger.handlers.clear()
    
    # コンソールハンドラー
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # ファイルハンドラー（JSON形式）
    file_handler = logging.handlers.RotatingFileHandler(
        settings.LOG_FILE,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(file_handler)
    
    # エラー専用ファイルハンドラー
    error_handler = logging.handlers.RotatingFileHandler(
        settings.LOG_FILE.replace('.log', '_error.log'),
        maxBytes=5*1024*1024,  # 5MB
        backupCount=10
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(error_handler)
    
    # セキュリティ専用ハンドラー
    security_logger = logging.getLogger('security')
    security_handler = logging.handlers.RotatingFileHandler(
        '/app/logs/security.log',
        maxBytes=5*1024*1024,
        backupCount=10
    )
    security_handler.setFormatter(JsonFormatter())
    security_logger.addHandler(security_handler)
    security_logger.setLevel(logging.INFO)
    security_logger.propagate = False  # 親ロガーに伝播しない
