import os
import yt_dlp
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from celery import current_task
from celery.exceptions import Retry
from celery.utils.log import get_task_logger

from ..core.celery_app import celery_app
from ..core.config import settings
from ..services.cache_service import CacheService
from ..services.file_service import FileService
from ..utils.helpers import sanitize_filename

# Celery 5.4の推奨ロガー使用
logger = get_task_logger(__name__)

# カスタム例外
class DownloadError(Exception):
    pass

class NetworkError(Exception):
    pass

@celery_app.task(
    bind=True,
    autoretry_for=(NetworkError, yt_dlp.DownloadError),
    retry_kwargs={'max_retries': 3, 'countdown': 60},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    acks_late=True,
    track_started=True,
    time_limit=3600,
    soft_time_limit=3300,
    priority=5,
)
def download_video(self, job_id: str, url: str, options: Dict[str, Any]):
    """動画ダウンロードタスク"""
    
    def update_job_status(job_id: str, status: str, data: Dict[str, Any]):
        """ジョブ状態更新（内部関数）"""
        try:
            import redis
            import json
            
            # 同期Redis接続
            redis_client = redis.from_url(settings.REDIS_URL)
            
            # 既存ジョブデータ取得
            existing_data = redis_client.get(f"job:{job_id}")
            if existing_data:
                job_data = json.loads(existing_data)
            else:
                job_data = {}
            
            # 状態更新
            job_data.update({
                "status": status,
                "updated_at": datetime.utcnow().isoformat(),
                "task_id": self.request.id,
                **data
            })
            
            if status == "running" and "started_at" not in job_data:
                job_data["started_at"] = datetime.utcnow().isoformat()
            
            # 保存
            redis_client.set(
                f"job:{job_id}",
                json.dumps(job_data, ensure_ascii=False, default=str),
                ex=86400  # 24時間
            )
            
        except Exception as e:
            logger.error(f"ジョブ状態更新エラー: {e}")
    
    try:
        logger.info(f"ダウンロード開始: {job_id}, URL: {url}")
        
        # タスク状態の更新
        self.update_state(
            state="PROGRESS",
            meta={
                "job_id": job_id,
                "stage": "initializing",
                "progress": 0,
                "current": 0,
                "total": 100,
                "started_at": datetime.utcnow().isoformat()
            }
        )
        
        # ジョブ状態更新
        update_job_status(job_id, "running", {"progress": 0})
        
        # ダウンロードオプション生成
        from ..services.video_service import VideoService
        video_service = VideoService()
        ydl_opts = video_service.get_download_options(options)
        
        # 出力ディレクトリ設定
        output_dir = os.path.join(settings.STORAGE_PATH, job_id)
        os.makedirs(output_dir, exist_ok=True)
        ydl_opts['outtmpl'] = os.path.join(output_dir, '%(title)s.%(ext)s')
        
        # 進捗コールバック
        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    if 'total_bytes' in d and d['total_bytes']:
                        progress = (d['downloaded_bytes'] / d['total_bytes']) * 100
                    elif '_percent_str' in d:
                        progress = float(d['_percent_str'].strip('%'))
                    else:
                        progress = None
                    
                    if progress:
                        # 新しいメタデータ形式で進捗更新
                        self.update_state(
                            state="PROGRESS",
                            meta={
                                "job_id": job_id,
                                "stage": "downloading",
                                "progress": min(progress, 99),
                                "current": d.get('downloaded_bytes', 0),
                                "total": d.get('total_bytes'),
                                "speed": d.get('speed'),
                                "eta": d.get('eta'),
                                "filename": d.get('filename', '')
                            }
                        )
                        
                        update_job_status(job_id, "running", {
                            "progress": min(progress, 99),
                            "downloaded_bytes": d.get('downloaded_bytes', 0),
                            "total_bytes": d.get('total_bytes'),
                            "speed": d.get('speed'),
                            "eta": d.get('eta')
                        })
                except Exception as e:
                    logger.warning(f"進捗更新エラー: {e}")
        
        ydl_opts['progress_hooks'] = [progress_hook]
        
        # ダウンロード実行
        downloaded_files = []
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # 情報取得段階
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "job_id": job_id,
                        "stage": "extracting_info",
                        "progress": 10
                    }
                )
                
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise DownloadError("動画情報を取得できませんでした")
                
                # ダウンロード段階
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "job_id": job_id,
                        "stage": "downloading",
                        "progress": 20,
                        "title": info.get('title', 'Unknown')
                    }
                )
                
                ydl.download([url])
                
                # ダウンロードされたファイルを探す
                for file_path in os.listdir(output_dir):
                    full_path = os.path.join(output_dir, file_path)
                    if os.path.isfile(full_path):
                        # ファイル名を安全に変換
                        safe_filename = sanitize_filename(file_path)
                        safe_path = os.path.join(settings.STORAGE_PATH, safe_filename)
                        
                        # ファイル移動
                        os.rename(full_path, safe_path)
                        downloaded_files.append(safe_filename)
                
                # 一時ディレクトリ削除
                import shutil
                shutil.rmtree(output_dir, ignore_errors=True)
                
                if not downloaded_files:
                    raise DownloadError("ダウンロードファイルが見つかりませんでした")
                
                # 結果保存
                result = {
                    "filename": downloaded_files[0],
                    "files": downloaded_files,
                    "title": info.get('title', 'Unknown'),
                    "duration": info.get('duration'),
                    "filesize": os.path.getsize(os.path.join(settings.STORAGE_PATH, downloaded_files[0])),
                    "completed_at": datetime.utcnow().isoformat(),
                    "task_id": self.request.id,
                    "retries": self.request.retries
                }
                
                # 最終更新
                self.update_state(
                    state="SUCCESS",
                    meta={
                        "job_id": job_id,
                        "stage": "completed",
                        "progress": 100,
                        "result": result
                    }
                )
                
                # ジョブ完了
                update_job_status(job_id, "success", {
                    "progress": 100,
                    "result": result
                })
                
                logger.info(f"ダウンロード完了: {job_id}, ファイル: {downloaded_files[0]}")
                return result
                
            except yt_dlp.DownloadError as e:
                error_msg = str(e)
                if "network" in error_msg.lower() or "timeout" in error_msg.lower():
                    logger.warning(f"ネットワークエラー、リトライします: {error_msg}")
                    raise NetworkError(error_msg)
                else:
                    raise DownloadError(error_msg)
            
    except (NetworkError, yt_dlp.DownloadError):
        # リトライ対象例外
        logger.warning(f"ダウンロードエラー（リトライ {self.request.retries + 1}/{self.max_retries}）: {job_id}")
        update_job_status(job_id, "retrying", {
            "retry_count": self.request.retries + 1,
            "error": "一時的なエラーが発生しました。リトライ中..."
        })
        raise
        
    except Exception as e:
        # リトライしない例外
        logger.error(f"ダウンロード失敗: {job_id}, エラー: {e}")
        
        # 失敗状態の更新
        self.update_state(
            state="FAILURE",
            meta={
                "job_id": job_id,
                "stage": "failed",
                "error": str(e),
                "completed_at": datetime.utcnow().isoformat()
            }
        )
        
        update_job_status(job_id, "failed", {
            "error": str(e),
            "completed_at": datetime.utcnow().isoformat()
        })
        
        # 一時ファイル削除
        try:
            output_dir = os.path.join(settings.STORAGE_PATH, job_id)
            if os.path.exists(output_dir):
                import shutil
                shutil.rmtree(output_dir, ignore_errors=True)
        except:
            pass
        
        raise

@celery_app.task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_kwargs={'max_retries': 2, 'countdown': 30},
    time_limit=60,
    priority=3
)
def webhook_notify(self, webhook_url: str, job_id: str, result: Dict[str, Any]):
    """Webhook通知タスク"""
    
    try:
        import requests
        
        payload = {
            "job_id": job_id,
            "status": "completed",
            "result": result,
            "timestamp": datetime.utcnow().isoformat(),
            "task_id": self.request.id
        }
        
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=30,
            headers={"Content-Type": "application/json"}
        )
        
        response.raise_for_status()
        logger.info(f"Webhook通知成功: {job_id} -> {webhook_url}")
        
        return {"status": "success", "response_code": response.status_code}
        
    except Exception as e:
        logger.error(f"Webhook通知失敗: {job_id}, {e}")
        raise
