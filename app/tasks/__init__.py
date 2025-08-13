"""
Celery タスク定義

このモジュールは非同期実行されるCeleryタスクを定義します。
動画ダウンロード、ファイルクリーンアップなどの重い処理を含みます。
"""

from .download_task import download_video
from .cleanup_task import cleanup_old_files

__all__ = ["download_video", "cleanup_old_files"]
