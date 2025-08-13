"""
ダウンロード API（完全版）
"""

from fastapi import APIRouter, HTTPException, Request
import uuid
import logging
from datetime import datetime

from ..models.job import DownloadRequest, JobResponse, JobStatus
from ..tasks.download_task import download_video
from ..services.cache_service import CacheService
from ..services.ticket_service import validate_ticket, get_job_limit
from ..utils.rate_limiter import smart_rate_limit
from ..utils.helpers import sanitize_url, generate_cache_key
from ..core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/download", response_model=JobResponse)
@smart_rate_limit("50/minute")  # レート制限を緩める
async def create_download_job(
    download_request: DownloadRequest,
    request: Request
):
    """動画ダウンロードジョブを作成"""
    
    try:
        # URL正規化
        clean_url = sanitize_url(str(download_request.url))
        client_ip = request.client.host
        
        # チケット検証
        ticket_valid = await validate_ticket(client_ip)
        max_jobs = await get_job_limit(ticket_valid)
        
        # 同時実行制限チェック
        from ..core.celery_app import celery_app
        inspect = celery_app.control.inspect()
        active_tasks = inspect.active() or {}
        running_jobs = sum(len(tasks) for tasks in active_tasks.values())
        
        if running_jobs >= max_jobs:
            raise HTTPException(
                status_code=429,
                detail=f"同時実行ジョブ数の上限（{max_jobs}）に達しています"
            )
        
        # キャッシュ確認
        cache_service = CacheService()
        
        request_data = {
            "url": str(download_request.url),
            "format_id": download_request.format_id,
            "quality": download_request.quality,
            "audio_only": download_request.audio_only,
            "subtitles": download_request.subtitles,
            "subtitle_lang": download_request.subtitle_lang,
            "webhook_url": str(download_request.webhook_url) if download_request.webhook_url else None
        }
        
        cache_key = generate_cache_key(clean_url, request_data)
        cached_result = await cache_service.get(cache_key)
        
        if cached_result:
            logger.info(f"キャッシュヒット - 既存結果を返却: {cache_key}")
            return JobResponse(
                job_id=cached_result["job_id"],
                status=JobStatus.SUCCESS,
                created_at=datetime.fromisoformat(cached_result["created_at"]),
                message="キャッシュから結果を取得しました"
            )
        
        # ジョブID生成
        job_id = str(uuid.uuid4())
        
        # ジョブ情報保存
        job_data = {
            "job_id": job_id,
            "url": clean_url,
            "options": request_data,
            "status": JobStatus.PENDING,
            "created_at": datetime.utcnow().isoformat(),
            "client_ip": client_ip,
            "premium": ticket_valid
        }
        
        await cache_service.set(f"job:{job_id}", job_data, expire=86400)
        
        # Celeryタスク実行
        task = download_video.delay(
            job_id=job_id,
            url=clean_url,
            options=request_data
        )
        
        logger.info(f"ダウンロードジョブ作成: {job_id}, URL: {clean_url}")
        
        return JobResponse(
            job_id=job_id,
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            message="ダウンロードジョブがキューに追加されました"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ジョブ作成エラー: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"ジョブ作成中にエラーが発生しました: {str(e)}"
        )

@router.post("/batch-download")
@smart_rate_limit("5/minute")
async def create_batch_download(
    request: Request,
    urls: list[DownloadRequest]
):
    """複数動画の一括ダウンロード（プレミアム機能）"""
    
    client_ip = request.client.host
    ticket_valid = await validate_ticket(client_ip)
    
    if not ticket_valid:
        raise HTTPException(
            status_code=403,
            detail="バッチダウンロードはプレミアム機能です"
        )
    
    if len(urls) > 10:
        raise HTTPException(
            status_code=400,
            detail="一度に処理できるURLは10個までです"
        )
    
    jobs = []
    for download_req in urls:
        try:
            job_response = await _create_single_job(download_req, client_ip, True)
            jobs.append(job_response.model_dump())
        except Exception as e:
            jobs.append({
                "error": str(e),
                "url": str(download_req.url)
            })
    
    return {"batch_jobs": jobs, "total": len(jobs)}

@router.get("/download/queue")
@smart_rate_limit("30/minute")
async def get_download_queue(request: Request):
    """ダウンロードキューの状態を取得"""
    
    try:
        from ..core.celery_app import celery_app
        inspect = celery_app.control.inspect()
        
        # アクティブタスク
        active_tasks = inspect.active() or {}
        active_count = sum(len(tasks) for tasks in active_tasks.values())
        
        # 待機中タスク
        reserved_tasks = inspect.reserved() or {}
        pending_count = sum(len(tasks) for tasks in reserved_tasks.values())
        
        # 登録済みタスク
        registered_tasks = inspect.registered() or {}
        worker_count = len(registered_tasks)
        
        return {
            "queue_status": {
                "active_jobs": active_count,
                "pending_jobs": pending_count,
                "worker_count": worker_count,
                "max_concurrent_premium": settings.MAX_CONCURRENT_JOBS_PREMIUM,
                "max_concurrent_normal": settings.MAX_CONCURRENT_JOBS_NORMAL
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"キュー状態取得エラー: {e}")
        raise HTTPException(
            status_code=500,
            detail="キュー状態取得中にエラーが発生しました"
        )

async def _create_single_job(download_request: DownloadRequest, client_ip: str, premium: bool):
    """内部使用：単一ジョブ作成"""
    clean_url = sanitize_url(str(download_request.url))
    job_id = str(uuid.uuid4())
    
    request_data = {
        "url": str(download_request.url),
        "format_id": download_request.format_id,
        "quality": download_request.quality,
        "audio_only": download_request.audio_only,
        "subtitles": download_request.subtitles,
        "subtitle_lang": download_request.subtitle_lang,
        "webhook_url": str(download_request.webhook_url) if download_request.webhook_url else None
    }
    
    cache_service = CacheService()
    job_data = {
        "job_id": job_id,
        "url": clean_url,
        "options": request_data,
        "status": JobStatus.PENDING,
        "created_at": datetime.utcnow().isoformat(),
        "client_ip": client_ip,
        "premium": premium
    }
    
    await cache_service.set(f"job:{job_id}", job_data, expire=86400)
    
    download_video.delay(
        job_id=job_id,
        url=clean_url,
        options=request_data
    )
    
    return JobResponse(
        job_id=job_id,
        status=JobStatus.PENDING,
        created_at=datetime.utcnow(),
        message="ジョブが作成されました"
    )
