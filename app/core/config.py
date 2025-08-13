import os
import warnings
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import List, Optional

class Settings(BaseSettings):
    """アプリケーション設定クラス（Pydantic V2対応）"""
    
    # Redis設定
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis接続URL")
    REDIS_RESULT_BACKEND: str = Field(default="redis://localhost:6379/1", description="Redis結果バックエンドURL")
    REDIS_PASSWORD: Optional[str] = Field(default=None, description="Redisパスワード")
    
    # Celery設定
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0", description="CeleryブローカーURL")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/1", description="Celery結果バックエンドURL")
    
    # API設定
    API_HOST: str = Field(default="0.0.0.0", description="APIホスト")
    API_PORT: int = Field(default=8000, ge=1, le=65535, description="APIポート")
    SECRET_KEY: str = Field(default="your-secret-key-change-this", description="アプリケーション秘密鍵")
    
    # ダウンロード設定
    STORAGE_PATH: str = Field(default="/app/downloads", description="ファイル保存パス")
    MAX_CONCURRENT_JOBS_PREMIUM: int = Field(default=10, ge=1, le=50, description="プレミアム最大同時ジョブ数")
    MAX_CONCURRENT_JOBS_NORMAL: int = Field(default=3, ge=1, le=20, description="通常最大同時ジョブ数")
    CACHE_TTL: int = Field(default=3600, ge=60, description="キャッシュ有効期限（秒）")
    
    # レート制限設定
    RATE_LIMIT_REQUESTS: int = Field(default=10, ge=1, le=1000, description="レート制限リクエスト数")
    RATE_LIMIT_WINDOW: int = Field(default=60, ge=1, description="レート制限時間窓（秒）")
    
    # ログ設定
    LOG_LEVEL: str = Field(default="INFO", description="ログレベル")
    LOG_FILE: str = Field(default="/app/logs/app.log", description="ログファイルパス")
    
    # プレミアムチケット設定
    PREMIUM_API_KEY: str = Field(default="your-premium-api-key-here", description="プレミアムAPIキー")
    
    # セキュリティ設定
    ALLOWED_HOSTS: str = Field(default="*", description="許可するホスト")
    
    # ファイルクリーンアップ設定
    CLEANUP_INTERVAL_HOURS: int = Field(default=24, ge=1, le=168, description="クリーンアップ間隔（時間）")
    MAX_FILE_AGE_DAYS: int = Field(default=7, ge=1, le=365, description="ファイル最大保持日数")
    MAX_STORAGE_GB: int = Field(default=100, ge=1, le=10000, description="最大ストレージ容量（GB）")
        
    # レート制限設定（段階的対応）
    ENABLE_RATE_LIMITING: bool = Field(default=True, description="レート制限有効化フラグ")
    
    # 通常ユーザー制限
    RATE_LIMIT_REQUESTS_NORMAL: int = Field(default=50, description="通常ユーザーレート制限")
    RATE_LIMIT_WINDOW_NORMAL: int = Field(default=60, description="通常ユーザー時間窓")
    
    # プレミアムユーザー制限
    RATE_LIMIT_REQUESTS_PREMIUM: int = Field(default=500, description="プレミアムユーザーレート制限")
    RATE_LIMIT_WINDOW_PREMIUM: int = Field(default=60, description="プレミアムユーザー時間窓")
    
    # 開発者制限（最も緩い）
    RATE_LIMIT_REQUESTS_DEVELOPER: int = Field(default=10000, description="開発者レート制限")
    RATE_LIMIT_WINDOW_DEVELOPER: int = Field(default=60, description="開発者時間窓")
    
    # 環境設定
    ENVIRONMENT: str = Field(default="development", description="実行環境")
    
    @field_validator('SECRET_KEY')
    @classmethod
    def validate_secret_key(cls, v):
        """SECRET_KEY検証"""
        if v == "your-secret-key-change-this":
            raise ValueError(
                "SECRET_KEYをデフォルト値から変更してください。"
            )
        
        if len(v) < 32:
            raise ValueError("SECRET_KEYは最低32文字以上である必要があります")
        
        if len(v) < 48:
            warnings.warn(
                "セキュリティ向上のため、SECRET_KEYは48文字以上を推奨します",
                UserWarning
            )
        
        return v
    
    @field_validator('LOG_LEVEL')
    @classmethod
    def validate_log_level(cls, v):
        """ログレベル検証"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVELは以下のいずれかである必要があります: {', '.join(valid_levels)}")
        return v.upper()
    
    def is_development(self) -> bool:
        """開発環境かどうか判定"""
        return self.ENVIRONMENT.lower() == 'development'
    
    def is_production(self) -> bool:
        """本番環境かどうか判定"""
        return self.ENVIRONMENT.lower() == 'production'
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "validate_assignment": True,
        "extra": "ignore",
    }

# 設定インスタンス作成
settings = Settings()

# 起動時の設定検証
def validate_settings():
    """設定の総合検証"""
    if settings.is_development():
        print("=== アプリケーション設定検証 ===")
        print("✅ SECRET_KEY: 設定済み" if settings.SECRET_KEY != "your-secret-key-change-this" else "⚠️ SECRET_KEY: デフォルト値")
        print("✅ PREMIUM_API_KEY: 設定済み" if settings.PREMIUM_API_KEY != "your-premium-api-key-here" else "⚠️ PREMIUM_API_KEY: デフォルト値")
        print(f"📝 環境: {'開発' if settings.is_development() else '本番'}")
        print(f"📊 ログレベル: {settings.LOG_LEVEL}")
        print(f"🔧 最大同時ジョブ数: Premium={settings.MAX_CONCURRENT_JOBS_PREMIUM}, Normal={settings.MAX_CONCURRENT_JOBS_NORMAL}")
        print(f"💾 ストレージパス: {settings.STORAGE_PATH}")
        print(f"🕐 キャッシュTTL: {settings.CACHE_TTL}秒")
        print(f"🚦 レート制限: {settings.RATE_LIMIT_REQUESTS}回/{settings.RATE_LIMIT_WINDOW}秒")
        print("=== 設定検証完了 ===")

# 開発環境のみで設定検証実行
if settings.is_development():
    validate_settings()
