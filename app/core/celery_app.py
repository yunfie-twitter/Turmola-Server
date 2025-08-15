"""
Celery アプリケーション設定（完全版）
"""

import os
import logging
from celery import Celery
from celery.signals import worker_ready, worker_shutdown

logger = logging.getLogger(__name__)

# 環境変数から設定を取得（フォールバック対応）
def get_celery_config():
    """Celery設定を安全に取得"""
    try:
        from .config import settings
        return {
            'broker_url': settings.CELERY_BROKER_URL,
            'result_backend': settings.CELERY_RESULT_BACKEND,
            'cleanup_interval': getattr(settings, 'CLEANUP_INTERVAL_HOURS', 24) * 3600.0
        }
    except ImportError:
        # settings が利用できない場合のデフォルト値
        return {
            'broker_url': os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0'),
            'result_backend': os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/1'),
            'cleanup_interval': 24 * 3600.0
        }

# 設定取得
config = get_celery_config()

# Celeryアプリケーション作成
celery_app = Celery(
    "turmola-server",
    broker=config['broker_url'],
    backend=config['result_backend'],
    include=[
        "app.tasks.download_task",
        "app.tasks.cleanup_task"
    ]
)

# Celery設定
celery_app.conf.update(
    # タスクシリアライゼーション設定
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_accept_content=["json"],
    
    # タイムゾーン設定
    timezone="Asia/Tokyo",
    enable_utc=True,
    
    # 結果設定
    result_expires=86400,  # 24時間
    result_backend_max_retries=3,
    result_backend_always_retry=True,
    
    # ワーカー設定
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
    
    # タスク設定
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,
    task_max_retries=3,
    
    # タスクルーティング
    task_routes={
        "app.tasks.download_task.download_video": {
            "queue": "download",
            "routing_key": "download"
        },
        "app.tasks.cleanup_task.*": {
            "queue": "cleanup",
            "routing_key": "cleanup"
        },
    },
    
    # キュー設定
    task_default_queue="default",
    task_default_exchange="default",
    task_default_exchange_type="direct",
    task_default_routing_key="default",
    
    # Beat設定（定期タスク）
    beat_schedule={
        "cleanup-old-files": {
            "task": "app.tasks.cleanup_task.cleanup_old_files",
            "schedule": config['cleanup_interval'],
            "options": {
                "queue": "cleanup",
                "routing_key": "cleanup"
            }
        },
        "system-health-check": {
            "task": "app.tasks.cleanup_task.system_health_check",
            "schedule": 300.0,  # 5分間隔
            "options": {
                "queue": "cleanup",
                "routing_key": "cleanup"
            }
        }
    },
    beat_scheduler="celery.beat:PersistentScheduler",
    beat_schedule_filename="/app/celerybeat/celerybeat-schedule",
    
    # Redis設定（ブローカーがRedisの場合）
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    
    # セキュリティ設定
    worker_hijack_root_logger=False,
    worker_log_color=False,
)

# イベントハンドラー
@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """ワーカー準備完了時の処理"""
    worker_name = sender.hostname if hasattr(sender, 'hostname') else 'unknown'
    logger.info(f"Celeryワーカーが準備完了: {worker_name}")
    
    # ワーカー統計情報をログ出力
    try:
        stats = sender.stats() if hasattr(sender, 'stats') else {}
        logger.info(f"ワーカー統計: {stats}")
    except Exception as e:
        logger.warning(f"ワーカー統計取得エラー: {e}")

@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwargs):
    """ワーカーシャットダウン時の処理"""
    worker_name = sender.hostname if hasattr(sender, 'hostname') else 'unknown'
    logger.info(f"Celeryワーカーがシャットダウン: {worker_name}")

# タスク完了時の処理
from celery.signals import task_success, task_failure, task_retry

@task_success.connect
def task_success_handler(sender=None, task_id=None, result=None, retries=None, einfo=None, **kwargs):
    """タスク成功時の処理"""
    logger.info(f"タスク成功: {sender.name}[{task_id}] - リトライ回数: {retries}")

@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwargs):
    """タスク失敗時の処理"""
    logger.error(f"タスク失敗: {sender.name}[{task_id}] - 例外: {exception}")

@task_retry.connect
def task_retry_handler(sender=None, task_id=None, reason=None, einfo=None, **kwargs):
    """タスクリトライ時の処理"""
    logger.warning(f"タスクリトライ: {sender.name}[{task_id}] - 理由: {reason}")

# アプリケーション起動時の初期化
def initialize_celery_app():
    """Celeryアプリケーション初期化"""
    try:
        # 設定検証
        logger.info("Celeryアプリケーション初期化開始")
        logger.info(f"ブローカーURL: {celery_app.conf.broker_url}")
        logger.info(f"結果バックエンド: {celery_app.conf.result_backend}")
        logger.info(f"含まれるタスクモジュール: {celery_app.conf.include}")
        
        # タスク自動検出
        celery_app.autodiscover_tasks()
        
        logger.info("Celeryアプリケーション初期化完了")
        return True
        
    except Exception as e:
        logger.error(f"Celeryアプリケーション初期化エラー: {e}")
        return False

# 初期化実行
if __name__ != "__main__":
    initialize_celery_app()
