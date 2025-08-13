"""
アプリケーションのコア設定モジュール

このモジュールはアプリケーションの基本設定、
Celery設定、Redis接続などの核心機能を提供します。
"""

from .config import settings
from .celery_app import celery_app
from .redis_client import redis_client

__all__ = ["settings", "celery_app", "redis_client"]
