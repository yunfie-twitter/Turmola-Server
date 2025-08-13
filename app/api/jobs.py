from fastapi import APIRouter, HTTPException, Query, Request, Response
import logging
from typing import Optional
from datetime import datetime
from celery.result import AsyncResult

from ..models.job import JobResult, JobStatus
from ..services.cache_service import CacheService
from ..services.file_service import FileService
from ..utils.rate_limiter import smart_rate_limit
from ..core.celery_app import celery_app
from ..core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/job/{job_id}/status", response_model=JobResult)
@smart_rate_limit("100/minute")  # ジョブ状態確認は頻繁に行われるため制限を緩める
async def get_job_status(job_id: str, request: Request):
    """ジョブ状態を取得"""
    
    try:
        # キャッシュからジョブ情報取得
        cache_service = CacheService()
        job_data = await cache_service.get(f"job:{job_id}")
        
        if not job_data:
            raise HTTPException(
                status_code=404,
                detail="ジョブが見つかりません"
            )
        
        # Celeryタスク状態確認
        task = AsyncResult(job_data.get("task_id", job_id), app=celery_app)
        
        # ステータス変換
        celery_status = task.status
        celery_result = task.result
        celery_info = task.info if hasattr(task, 'info') else {}
        
        if celery_status == "PENDING":
            status = JobStatus.PENDING
        elif celery_status in ["STARTED", "PROGRESS"]:
            status = JobStatus.RUNNING
        elif celery_status == "SUCCESS":
            status = JobStatus.SUCCESS
        elif celery_status == "FAILURE":
            status = JobStatus.FAILED
        elif celery_status == "RETRY":
            status = JobStatus.RETRYING
        else:
            status = JobStatus.PENDING
        
        # 進捗情報取得
        progress = None
        stage = None
        
        if isinstance(celery_info, dict):
            progress = celery_info.get("progress")
            stage = celery_info.get("stage")
        elif isinstance(celery_result, dict):
            progress = celery_result.get("progress")
            stage = celery_result.get("stage")
        
        # ダウンロードURL生成
        download_url = None
        file_info = None
        
        if status == JobStatus.SUCCESS:
            result_data = None
            if isinstance(celery_info, dict) and "result" in celery_info:
                result_data = celery_info["result"]
            elif isinstance(celery_result, dict) and "filename" in celery_result:
                result_data = celery_result
            
            if result_data and "filename" in result_data:
                filename = result_data["filename"]
                download_url = f"/api/job/{job_id}/file"
                
                # ファイル情報取得
                file_service = FileService()
                file_info = await file_service.get_file_info(filename)
        
        # エラー情報
        error = None
        if status == JobStatus.FAILED:
            if isinstance(celery_info, dict) and "error" in celery_info:
                error = celery_info["error"]
            elif isinstance(celery_result, Exception):
                error = str(celery_result)
            elif isinstance(celery_result, dict) and "error" in celery_result:
                error = celery_result["error"]
        
        return JobResult(
            job_id=job_id,
            status=status,
            created_at=datetime.fromisoformat(job_data.get("created_at")),
            started_at=datetime.fromisoformat(job_data.get("started_at")) if job_data.get("started_at") else None,
            completed_at=datetime.fromisoformat(job_data.get("completed_at")) if job_data.get("completed_at") else None,
            progress=progress,
            result=celery_result if isinstance(celery_result, dict) else None,
            error=error,
            retry_count=getattr(task, 'retries', 0),
            download_url=download_url,
            file_info=file_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ジョブ状態取得エラー: {e}")
        raise HTTPException(
            status_code=500,
            detail="ジョブ状態取得中にエラーが発生しました"
        )

@router.get("/job/{job_id}/file")
@smart_rate_limit("20/minute")
async def download_job_file(job_id: str, request: Request):
    """完了したジョブのファイルをダウンロード（日本語ファイル名対応版）"""
    
    try:
        # ジョブ状態確認
        cache_service = CacheService()
        job_data = await cache_service.get(f"job:{job_id}")
        
        if not job_data:
            raise HTTPException(
                status_code=404,
                detail="ジョブが見つかりません"
            )
        
        # ジョブの完了確認
        if job_data.get("status") != "success":
            raise HTTPException(
                status_code=400,
                detail="ジョブが完了していません"
            )
        
        # ファイル名取得
        result = job_data.get("result", {})
        filename = result.get("filename")
        
        if not filename:
            raise HTTPException(
                status_code=404,
                detail="ダウンロードファイルが見つかりません"
            )
        
        # 安全なファイルパス構築
        import os
        from pathlib import Path
        import urllib.parse
        
        # STORAGE_PATHをPathオブジェクトに変換
        storage_path = Path(settings.STORAGE_PATH)
        file_path = storage_path / filename
        
        # セキュリティチェック（ディレクトリトラバーサル防止）
        try:
            file_path = file_path.resolve()
            storage_path = storage_path.resolve()
            
            if not str(file_path).startswith(str(storage_path)):
                raise HTTPException(
                    status_code=403,
                    detail="不正なファイルパスです"
                )
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="ファイルパスが不正です"
            )
        
        # ファイル存在確認
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(
                status_code=404,
                detail="ファイルが存在しません"
            )
        
        # MIMEタイプ自動判定
        import mimetypes
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = 'application/octet-stream'
        
        # 日本語ファイル名のエンコーディング処理
        # RFC 5987形式でエンコード
        encoded_filename = urllib.parse.quote(filename, safe='')
        
        # ブラウザ互換性のためのファイル名設定
        content_disposition = f"attachment; filename*=UTF-8''{encoded_filename}"
        
        # ASCII文字のみのfallback名も追加
        ascii_filename = "".join(c for c in filename if ord(c) < 128) or "downloaded_file"
        if ascii_filename != filename:
            content_disposition = f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}'
        
        # ファイル配信
        from fastapi.responses import FileResponse
        
        return FileResponse(
            path=str(file_path),
            filename=ascii_filename,  # ASCII互換のファイル名を使用
            media_type=mime_type,
            headers={
                "Content-Disposition": content_disposition,
                "Content-Type": mime_type,
                "Cache-Control": "no-cache"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ファイルダウンロードエラー: {e}")
        raise HTTPException(
            status_code=500,
            detail="ファイルダウンロード中にエラーが発生しました"
        )

@router.delete("/job/{job_id}")
@smart_rate_limit("30/minute")
async def cancel_job(job_id: str, request: Request):
    """ジョブをキャンセル"""
    
    try:
        # ジョブ存在確認
        cache_service = CacheService()
        job_data = await cache_service.get(f"job:{job_id}")
        
        if not job_data:
            raise HTTPException(
                status_code=404,
                detail="ジョブが見つかりません"
            )
        
        # タスクキャンセル
        task_id = job_data.get("task_id", job_id)
        celery_app.control.revoke(task_id, terminate=True)
        
        # ジョブ状態更新
        job_data["status"] = "cancelled"
        job_data["cancelled_at"] = datetime.utcnow().isoformat()
        
        await cache_service.set(f"job:{job_id}", job_data, expire=86400)
        
        logger.info(f"ジョブキャンセル: {job_id}")
        
        return {
            "job_id": job_id,
            "status": "cancelled",
            "message": "ジョブがキャンセルされました"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ジョブキャンセルエラー: {e}")
        raise HTTPException(
            status_code=500,
            detail="ジョブキャンセル中にエラーが発生しました"
        )

@router.get("/jobs")
@smart_rate_limit("20/minute")
async def get_job_list(
    request: Request,
    status: Optional[str] = Query(None, description="ステータスフィルター"),
    limit: int = Query(10, ge=1, le=100, description="取得件数"),
    offset: int = Query(0, ge=0, description="オフセット")
):
    """ジョブ一覧を取得（管理者用）"""
    
    try:
        # 管理者認証チェック（簡易版）
        api_key = request.headers.get("X-Admin-Key")
        if api_key != getattr(settings, 'ADMIN_API_KEY', None):
            raise HTTPException(
                status_code=403,
                detail="管理者権限が必要です"
            )
        
        # Redisからジョブ一覧取得（実装は簡略化）
        cache_service = CacheService()
        # 実際の実装ではRedisのSCANコマンドなどを使用
        
        return {
            "jobs": [],  # 実装時はジョブデータを返却
            "total": 0,
            "limit": limit,
            "offset": offset,
            "message": "ジョブ一覧取得（実装中）"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ジョブ一覧取得エラー: {e}")
        raise HTTPException(
            status_code=500,
            detail="ジョブ一覧取得中にエラーが発生しました"
        )
