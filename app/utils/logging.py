import logging
import logging.handlers
import os
from datetime import datetime
from ..core.config import settings

def setup_logging():
    """ログ設定を初期化"""
    
    # ログディレクトリ作成
    log_dir = os.path.dirname(settings.LOG_FILE)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # ルートロガー設定
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))
    
    # ハンドラーが既に設定されている場合はスキップ
    if root_logger.handlers:
        return
    
    # フォーマッター
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # コンソールハンドラー
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # ファイルハンドラー（ローテート）
    file_handler = logging.handlers.RotatingFileHandler(
        settings.LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, settings.LOG_LEVEL))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # 特定ロガーの設定
    # Celeryログ
    celery_logger = logging.getLogger('celery')
    celery_logger.setLevel(logging.INFO)
    
    # yt-dlpログ（警告レベル以上のみ）
    yt_dlp_logger = logging.getLogger('yt_dlp')
    yt_dlp_logger.setLevel(logging.WARNING)
    
    # Redisログ
    redis_logger = logging.getLogger('redis')
    redis_logger.setLevel(logging.WARNING)
    
    logging.info("ログ設定が完了しました")

class SecurityLogger:
    """セキュリティ関連のログ"""
    
    def __init__(self):
        self.logger = logging.getLogger('security')
        self.logger.setLevel(logging.INFO)
        
        # セキュリティログ専用ファイルハンドラー
        security_log_file = os.path.join(
            os.path.dirname(settings.LOG_FILE),
            'security.log'
        )
        
        security_handler = logging.handlers.RotatingFileHandler(
            security_log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=20,
            encoding='utf-8'
        )
        
        security_formatter = logging.Formatter(
            '%(asctime)s - SECURITY - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        security_handler.setFormatter(security_formatter)
        
        if not self.logger.handlers:
            self.logger.addHandler(security_handler)
    
    def log_suspicious_access(self, ip: str, user_agent: str, endpoint: str, reason: str):
        """不審なアクセスをログ記録"""
        self.logger.warning(
            f"SUSPICIOUS_ACCESS - IP: {ip}, UserAgent: {user_agent}, "
            f"Endpoint: {endpoint}, Reason: {reason}"
        )
    
    def log_rate_limit_exceeded(self, ip: str, endpoint: str, limit: str):
        """レート制限超過をログ記録"""
        self.logger.warning(
            f"RATE_LIMIT_EXCEEDED - IP: {ip}, Endpoint: {endpoint}, Limit: {limit}"
        )
    
    def log_authentication_failure(self, ip: str, reason: str):
        """認証失敗をログ記録"""
        self.logger.warning(
            f"AUTH_FAILURE - IP: {ip}, Reason: {reason}"
        )
    
    def log_blocked_request(self, ip: str, reason: str):
        """ブロックされたリクエストをログ記録"""
        self.logger.error(
            f"BLOCKED_REQUEST - IP: {ip}, Reason: {reason}"
        )

class JobLogger:
    """ジョブ関連のログ"""
    
    def __init__(self):
        self.logger = logging.getLogger('jobs')
        self.logger.setLevel(logging.INFO)
        
        # ジョブログ専用ファイルハンドラー
        job_log_file = os.path.join(
            os.path.dirname(settings.LOG_FILE),
            'jobs.log'
        )
        
        job_handler = logging.handlers.RotatingFileHandler(
            job_log_file,
            maxBytes=20 * 1024 * 1024,  # 20MB
            backupCount=30,
            encoding='utf-8'
        )
        
        job_formatter = logging.Formatter(
            '%(asctime)s - JOB - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        job_handler.setFormatter(job_formatter)
        
        if not self.logger.handlers:
            self.logger.addHandler(job_handler)
    
    def log_job_created(self, job_id: str, url: str, client_ip: str):
        """ジョブ作成をログ記録"""
        self.logger.info(
            f"JOB_CREATED - JobID: {job_id}, URL: {url}, ClientIP: {client_ip}"
        )
    
    def log_job_started(self, job_id: str):
        """ジョブ開始をログ記録"""
        self.logger.info(f"JOB_STARTED - JobID: {job_id}")
    
    def log_job_completed(self, job_id: str, filename: str, duration: float):
        """ジョブ完了をログ記録"""
        self.logger.info(
            f"JOB_COMPLETED - JobID: {job_id}, File: {filename}, Duration: {duration:.2f}s"
        )
    
    def log_job_failed(self, job_id: str, error: str, retry_count: int):
        """ジョブ失敗をログ記録"""
        self.logger.error(
            f"JOB_FAILED - JobID: {job_id}, Error: {error}, Retries: {retry_count}"
        )
    
    def log_job_progress(self, job_id: str, progress: float):
        """ジョブ進捗をログ記録（デバッグレベル）"""
        self.logger.debug(
            f"JOB_PROGRESS - JobID: {job_id}, Progress: {progress:.1f}%"
        )

# グローバルロガーインスタンス
security_logger = SecurityLogger()
job_logger = JobLogger()

def get_security_logger() -> SecurityLogger:
    """セキュリティロガーを取得"""
    return security_logger

def get_job_logger() -> JobLogger:
    """ジョブロガーを取得"""
    return job_logger
