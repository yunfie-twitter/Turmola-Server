"""
Turmola API Application

FastAPI + Celery + Redis を使用した動画ダウンロードAPI
"""

__version__ = "1.0.0"
__description__ = "yt-dlpを使用した非同期動画ダウンロードAPI"

from .core.config import settings

# アプリケーション初期化時の設定確認
if not settings.SECRET_KEY or settings.SECRET_KEY == "your-secret-key-change-this":
    import warnings
    warnings.warn("SECRET_KEYが設定されていません。本番環境では必ず変更してください。")

# ログディレクトリの作成
import os
log_dir = os.path.dirname(settings.LOG_FILE)
if not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

# ダウンロードディレクトリの作成
if not os.path.exists(settings.STORAGE_PATH):
    os.makedirs(settings.STORAGE_PATH, exist_ok=True)
