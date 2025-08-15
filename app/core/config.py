"""
アプリケーション設定（Pydantic V2完全対応版）
"""

import os
import warnings
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import List, Optional
from pathlib import Path

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
    SECRET_KEY: str = Field(default="development-key-change-in-production", description="アプリケーション秘密鍵")
    
    # ダウンロード設定
    STORAGE_PATH: str = Field(default="/app/downloads", description="ファイル保存パス")
    MAX_CONCURRENT_JOBS_PREMIUM: int = Field(default=10, ge=1, le=50, description="プレミアム最大同時ジョブ数")
    MAX_CONCURRENT_JOBS_NORMAL: int = Field(default=3, ge=1, le=20, description="通常最大同時ジョブ数")
    CACHE_TTL: int = Field(default=3600, ge=60, description="キャッシュ有効期限（秒）")
    
    # レート制限設定
    ENABLE_RATE_LIMITING: bool = Field(default=True, description="レート制限有効化フラグ")
    RATE_LIMIT_REQUESTS: int = Field(default=10, ge=1, le=1000, description="レート制限リクエスト数")
    RATE_LIMIT_WINDOW: int = Field(default=60, ge=1, description="レート制限時間窓（秒）")
    
    # ログ設定
    LOG_LEVEL: str = Field(default="INFO", description="ログレベル")
    LOG_FILE: str = Field(default="/app/logs/app.log", description="ログファイルパス")
    
    # プレミアムチケット設定
    PREMIUM_API_KEY: str = Field(default="development-premium-key", description="プレミアムAPIキー")
    
    # セキュリティ設定
    ALLOWED_HOSTS: str = Field(default="*", description="許可するホスト")
    
    # ファイルクリーンアップ設定
    CLEANUP_INTERVAL_HOURS: int = Field(default=24, ge=1, le=168, description="クリーンアップ間隔（時間）")
    MAX_FILE_AGE_DAYS: int = Field(default=7, ge=1, le=365, description="ファイル最大保持日数")
    MAX_STORAGE_GB: int = Field(default=100, ge=1, le=10000, description="最大ストレージ容量（GB）")
    
    # 追加: フェイルオーバー設定
    ENABLE_FAILOVER: bool = False
    
    # 追加: その他の高度な機能設定
    ENABLE_ARIA2: bool = False
    ENABLE_RATE_LIMITING: bool = False
    ENABLE_PERFORMANCE_MONITORING: bool = False
    
    # 環境設定
    ENVIRONMENT: str = Field(default="development", description="実行環境")
    
    @field_validator('SECRET_KEY')
    @classmethod
    def validate_secret_key(cls, v):
        """SECRET_KEY検証（開発環境では緩和）"""
        if v in ["your-secret-key-here-change-this-in-production-minimum-48-characters", 
                 "development-key-change-in-production"]:
            warnings.warn(
                "開発用のデフォルトSECRET_KEYを使用しています。本番環境では必ず変更してください。",
                UserWarning
            )
            # 開発環境では警告のみで続行
            return v
            
        if len(v) < 32:
            raise ValueError("SECRET_KEYは最低32文字以上である必要があります")
        
        return v
    
    @field_validator('LOG_LEVEL')
    @classmethod
    def validate_log_level(cls, v):
        """ログレベル検証"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVELは以下のいずれかである必要があります: {', '.join(valid_levels)}")
        return v.upper()
    
    @field_validator('PREMIUM_API_KEY')
    @classmethod
    def validate_premium_api_key(cls, v):
        """PREMIUM_API_KEY検証（開発環境では緩和）"""
        if v in ["your-premium-api-key-here-change-this-minimum-32-characters",
                 "development-premium-key"]:
            warnings.warn(
                "開発用のデフォルトPREMIUM_API_KEYを使用しています。本番環境では必ず変更してください。",
                UserWarning
            )
            # 開発環境では警告のみで続行
            return v
        
        if len(v) < 16:  # 開発環境では16文字以上で許可
            raise ValueError("PREMIUM_API_KEYは最低16文字以上である必要があります")
        
        return v
    
    # 重要: 環境判定メソッドを追加
    def is_development(self) -> bool:
        """開発環境かどうか判定"""
        return self.ENVIRONMENT.lower() in ['development', 'dev']
    
    def is_production(self) -> bool:
        """本番環境かどうか判定"""
        return self.ENVIRONMENT.lower() in ['production', 'prod']
    
    def get_storage_path(self) -> Path:
        """ストレージパスをPathオブジェクトで取得"""
        return Path(self.STORAGE_PATH)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "validate_assignment": True,
        "extra": "ignore",
    }

# 設定インスタンス作成
settings = Settings()

# 起動時の設定検証（エラー安全版）
def validate_settings():
    """設定の総合検証"""
    try:
        if settings.is_development():
            print("=== アプリケーション設定検証 ===")
            print(f"🔧 環境: {'開発' if settings.is_development() else '本番'}")
            print(f"📊 ログレベル: {settings.LOG_LEVEL}")
            print(f"🚦 レート制限: {'有効' if settings.ENABLE_RATE_LIMITING else '無効'}")
            print(f"💾 ストレージパス: {settings.STORAGE_PATH}")
            print("=== 設定検証完了 ===")
    except Exception as e:
        print(f"⚠️ 設定検証エラー: {e}")

# 条件付きで設定検証実行
try:
    validate_settings()
except Exception:
    # 設定検証でエラーが出ても起動は継続
    pass
