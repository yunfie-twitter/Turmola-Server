from celery import Celery
from kombu import Queue
import os
import logging

from .config import settings

# Celeryアプリケーション初期化
celery_app = Celery(
    "video_downloader",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

# タスクの自動検出設定
celery_app.autodiscover_tasks([
    "app.tasks.download_task",
    "app.tasks.cleanup_task"
])

# Celery設定（5.4以降の推奨設定）
celery_app.conf.update(
    # タスク設定
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Tokyo",
    enable_utc=True,
    
    # 結果設定
    task_track_started=True,
    result_extended=True,  # 5.4で追加された拡張結果情報
    result_expires=86400,  # 24時間
    result_persistent=True,
    result_chord_join_timeout=3600,  # コード結合タイムアウト
    
    # ワーカー設定（メモリリーク防止）
    worker_max_tasks_per_child=1000,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_pool_restarts=True,  # 5.4で改善されたワーカープール再起動
    
    # リトライ設定
    task_default_retry_delay=60,
    task_max_retries=3,
    task_retry_jitter=True,
    task_retry_backoff=2,  # 指数バックオフ
    task_retry_backoff_max=600,  # 最大リトライ間隔
    
    # キュー設定
    task_routes={
        "app.tasks.download_task.download_video": {"queue": "download"},
        "app.tasks.cleanup_task.cleanup_old_files": {"queue": "cleanup"},
        "app.tasks.cleanup_task.cleanup_old_files_sync": {"queue": "cleanup"},
        "app.tasks.cleanup_task.monitor_storage_usage": {"queue": "cleanup"},
        "app.tasks.cleanup_task.monitor_storage_usage_sync": {"queue": "cleanup"},
    },
    
    # 並行実行制限
    worker_concurrency=4,
    
    # 新しいタスク実行設定（5.4以降）
    task_always_eager=False,
    task_store_eager_result=True,
    task_eager_propagates=True,
    
    # セキュリティ設定
    worker_hijack_root_logger=False,
    worker_log_color=False,
    
    # Beat設定（スケジュールタスク）
    beat_schedule={
        "cleanup-old-files": {
            "task": "app.tasks.cleanup_task.cleanup_old_files_sync",
            "schedule": settings.CLEANUP_INTERVAL_HOURS * 3600.0,
            "options": {"queue": "cleanup"}
        },
        "monitor-storage": {
            "task": "app.tasks.cleanup_task.monitor_storage_usage_sync",
            "schedule": 3600.0,  # 1時間ごと
            "options": {"queue": "cleanup"}
        },
    },
    beat_scheduler="celery.beat:PersistentScheduler",
    beat_schedule_filename="celerybeat-schedule",
    
    # ブローカー設定
    broker_connection_retry=True,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=None,
    
    # 監視設定
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # タスク結果バックエンド設定
    result_backend_transport_options={
        "master_name": "mymaster",
        "retry_on_timeout": True,
        "retry_on_error": [ConnectionError, TimeoutError],
    }
)

# キュー定義（5.4以降の推奨設定）
celery_app.conf.task_queues = (
    Queue(
        "download", 
        routing_key="download",
        queue_arguments={"x-max-priority": 10}
    ),
    Queue(
        "cleanup", 
        routing_key="cleanup",
        queue_arguments={"x-max-priority": 5}
    ),
)

# 新しいシグナルハンドラー（5.4以降）
from celery.signals import (
    after_setup_logger,
    after_setup_task_logger,
    worker_ready,
    worker_shutting_down
)

@after_setup_logger.connect
def setup_loggers(logger, *args, **kwargs):
    """ロガー設定"""
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if logger.handlers:
        for handler in logger.handlers:
            handler.setFormatter(formatter)

@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """ワーカー準備完了時の処理"""
    logger = logging.getLogger(__name__)
    logger.info(f"Celeryワーカーが準備完了: {sender}")

@worker_shutting_down.connect
def worker_shutting_down_handler(sender=None, **kwargs):
    """ワーカー終了時の処理"""
    logger = logging.getLogger(__name__)
    logger.info(f"Celeryワーカーが終了中: {sender}")

# 非推奨の設定を削除・更新
# 5.4では以下の設定が非推奨または変更されています
# - worker_pool_restarts (新設定で置き換え)
# - task_store_eager_result (デフォルトでTrue)
