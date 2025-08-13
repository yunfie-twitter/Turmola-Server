"""
カスタム例外クラス（Celery対応版）
"""

class TurmolaException(Exception):
    """Turmola基底例外クラス"""
    def __init__(self, message: str, code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}

class VideoNotFoundError(TurmolaException):
    """動画が見つからない場合の例外"""
    pass

class DownloadTimeoutError(TurmolaException):
    """ダウンロードタイムアウト例外"""
    pass

class StorageFullError(TurmolaException):
    """ストレージ容量不足例外"""
    pass

class RateLimitExceededError(TurmolaException):
    """レート制限超過例外"""
    pass

class NetworkError(TurmolaException):
    """ネットワークエラー例外"""
    pass

class UnsupportedFormatError(TurmolaException):
    """サポートされていないフォーマット例外"""
    pass

class AuthenticationError(TurmolaException):
    """認証エラー例外"""
    pass
