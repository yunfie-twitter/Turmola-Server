"""
動画ダウンロードタスク（完全修正版）
"""

import os
import yt_dlp
import logging
from datetime import datetime
from typing import Dict, Any
from celery import current_task

from ..core.celery_app import celery_app
from ..core.config import settings
from ..services.video_service import VideoService
from ..utils.helpers import get_safe_filename_with_fallback, generate_unique_filename

logger = logging.getLogger(__name__)

@celery_app.task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
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
    """動画ダウンロードタスク（完全修正版）"""
    
    def update_job_status(job_id: str, status: str, data: Dict[str, Any]):
        """ジョブ状態更新"""
        try:
            import redis
            import json
            
            redis_client = redis.from_url(settings.REDIS_URL)
            existing_data = redis_client.get(f"job:{job_id}")
            if existing_data:
                job_data = json.loads(existing_data)
            else:
                job_data = {}
            
            job_data.update({
                "status": status,
                "updated_at": datetime.utcnow().isoformat(),
                "task_id": self.request.id,
                **data
            })
            
            if status == "running" and "started_at" not in job_data:
                job_data["started_at"] = datetime.utcnow().isoformat()
            
            redis_client.set(
                f"job:{job_id}",
                json.dumps(job_data, ensure_ascii=False, default=str),
                ex=86400
            )
            
        except Exception as e:
            logger.error(f"ジョブ状態更新エラー: {e}")
    
    try:
        logger.info(f"ダウンロード開始: {job_id}, URL: {url}")
        
        # YouTube判別
        video_service = VideoService()
        is_youtube = video_service.is_youtube_url(url)
        
        logger.info(f"サイト判別: {'YouTube' if is_youtube else 'その他のサイト'} - {url}")
        
        # タスク状態の更新
        self.update_state(
            state="PROGRESS",
            meta={
                "job_id": job_id,
                "stage": "initializing",
                "progress": 0,
                "site_type": "youtube" if is_youtube else "other",
                "started_at": datetime.utcnow().isoformat()
            }
        )
        
        update_job_status(job_id, "running", {
            "progress": 0,
            "site_type": "youtube" if is_youtube else "other"
        })
        
        if is_youtube:
            return _download_youtube_video(self, job_id, url, options, update_job_status)
        else:
            return _download_other_site_video(self, job_id, url, options, update_job_status)
        
    except Exception as e:
        # 標準例外のみ使用（Celeryシリアライゼーション対応）
        error_message = str(e)
        logger.error(f"ダウンロード失敗: {job_id}, エラー: {error_message}")
        
        self.update_state(
            state="FAILURE",
            meta={
                "job_id": job_id,
                "stage": "failed",
                "error": error_message,
                "completed_at": datetime.utcnow().isoformat()
            }
        )
        
        update_job_status(job_id, "failed", {
            "error": error_message,
            "completed_at": datetime.utcnow().isoformat()
        })
        
        # 標準例外として再発生
        raise Exception(error_message)

def _download_youtube_video(task, job_id: str, url: str, options: Dict[str, Any], update_job_status):
    """YouTube動画ダウンロード処理"""
    
    logger.info(f"YouTube動画処理開始: {job_id}")
    
    video_service = VideoService()
    ydl_opts = video_service.get_download_options(options, url)
    
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
                    task.update_state(
                        state="PROGRESS",
                        meta={
                            "job_id": job_id,
                            "stage": "downloading",
                            "progress": min(progress, 99),
                            "site_type": "youtube"
                        }
                    )
            except Exception as e:
                logger.warning(f"進捗更新エラー: {e}")
    
    ydl_opts['progress_hooks'] = [progress_hook]
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if not info:
            raise Exception("YouTube動画情報を取得できませんでした")
        
        ydl.download([url])
        
        # ファイル処理（日本語ファイル名対応）
        downloaded_files = _process_downloaded_files(output_dir, job_id, info)
        
        if not downloaded_files:
            raise Exception("ダウンロードファイルが見つかりませんでした")
        
        result = {
            "filename": downloaded_files[0],
            "files": downloaded_files,
            "title": info.get('title', 'Unknown'),
            "duration": info.get('duration'),
            "filesize": os.path.getsize(os.path.join(settings.STORAGE_PATH, downloaded_files[0])),
            "completed_at": datetime.utcnow().isoformat(),
            "site_type": "youtube"
        }
        
        task.update_state(state="SUCCESS", meta={"job_id": job_id, "result": result})
        update_job_status(job_id, "success", {"result": result})
        logger.info(f"YouTube動画ダウンロード完了: {job_id}")
        
        return result

def _download_other_site_video(task, job_id: str, url: str, options: Dict[str, Any], update_job_status):
    """その他サイト動画ダウンロード処理（ニコニコ動画強化版）"""
    
    logger.info(f"その他サイト動画処理開始: {job_id}")
    
    video_service = VideoService()
    ydl_opts = video_service.get_download_options(options, url)
    
    # 出力ディレクトリ設定
    output_dir = os.path.join(settings.STORAGE_PATH, job_id)
    os.makedirs(output_dir, exist_ok=True)
    ydl_opts['outtmpl'] = os.path.join(output_dir, '%(title)s.%(ext)s')
    
    # フォーマット再試行パターン（ニコニコ動画特化）
    format_attempts = [
        'best[height<=480]',  # 480p以下
        'worst',              # 最低品質
        'best',               # 最高品質
        None                  # デフォルト
    ]
    
    last_error = None
    
    for attempt, format_override in enumerate(format_attempts):
        try:
            logger.info(f"試行 {attempt + 1}/{len(format_attempts)}: フォーマット={format_override}")
            
            # フォーマット設定
            if format_override is not None:
                ydl_opts['format'] = format_override
            elif 'format' in ydl_opts:
                del ydl_opts['format']
            
            # 進捗コールバック
            def progress_hook(d):
                if d['status'] == 'downloading':
                    try:
                        task.update_state(
                            state="PROGRESS",
                            meta={
                                "job_id": job_id,
                                "stage": "downloading",
                                "site_type": "other"
                            }
                        )
                    except Exception:
                        pass
            
            ydl_opts['progress_hooks'] = [progress_hook]
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # 情報取得
                info = ydl.extract_info(url, download=False)
                if not info:
                    last_error = "動画情報を取得できませんでした"
                    continue
                
                # ダウンロード実行
                ydl.download([url])
                
                # ファイル処理（日本語ファイル名対応）
                downloaded_files = _process_downloaded_files(output_dir, job_id, info)
                
                if not downloaded_files:
                    last_error = "ダウンロードファイルが見つかりませんでした"
                    continue
                
                # 成功時の結果
                result = {
                    "filename": downloaded_files[0],
                    "files": downloaded_files,
                    "title": info.get('title', 'Unknown'),
                    "duration": info.get('duration'),
                    "filesize": os.path.getsize(os.path.join(settings.STORAGE_PATH, downloaded_files[0])),
                    "completed_at": datetime.utcnow().isoformat(),
                    "site_type": "other",
                    "retry_count": attempt + 1,
                    "successful_format": format_override or "default"
                }
                
                task.update_state(state="SUCCESS", meta={"job_id": job_id, "result": result})
                update_job_status(job_id, "success", {"result": result})
                logger.info(f"その他サイト動画ダウンロード完了: {job_id} (試行{attempt + 1}回)")
                
                return result
                
        except Exception as e:
            last_error = str(e)
            logger.warning(f"試行 {attempt + 1} 失敗: {last_error}")
            continue
    
    # すべての試行が失敗した場合
    logger.error(f"すべての試行が失敗: {job_id}, 最終エラー: {last_error}")
    raise Exception(f"ダウンロードに失敗しました: {last_error}")

def _process_downloaded_files(output_dir: str, job_id: str, video_info: Dict[str, Any] = None):
    """ダウンロードファイル処理（日本語ファイル名対応）"""
    downloaded_files = []
    
    if not os.path.exists(output_dir):
        return downloaded_files
    
    for file_path in os.listdir(output_dir):
        full_path = os.path.join(output_dir, file_path)
        if os.path.isfile(full_path) and os.path.getsize(full_path) > 0:
            
            # 日本語対応ファイル名生成
            safe_filename = get_safe_filename_with_fallback(file_path, video_info)
            
            # 重複チェック
            safe_filename = generate_unique_filename(safe_filename, settings.STORAGE_PATH)
            
            safe_path = os.path.join(settings.STORAGE_PATH, safe_filename)
            os.rename(full_path, safe_path)
            downloaded_files.append(safe_filename)
            
            logger.info(f"ファイル保存: {file_path} -> {safe_filename}")
    
    # 一時ディレクトリ削除
    import shutil
    shutil.rmtree(output_dir, ignore_errors=True)
    
    return downloaded_files
