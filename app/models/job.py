"""
ジョブ関連のデータモデル
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
import uuid

class JobStatus(str, Enum):
    """ジョブステータス"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"

class VideoFormat(BaseModel):
    """動画フォーマット情報"""
    format_id: str
    ext: str
    resolution: Optional[str] = None
    fps: Optional[int] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None
    filesize: Optional[int] = None

class DownloadRequest(BaseModel):
    """ダウンロードリクエスト"""
    url: HttpUrl = Field(..., description="動画URL")
    format_id: Optional[str] = Field(None, description="動画フォーマットID")
    quality: Optional[str] = Field("best", description="画質 (best/worst/720p等)")
    audio_only: bool = Field(False, description="音声のみダウンロード")
    subtitles: bool = Field(False, description="字幕ダウンロード")
    subtitle_lang: Optional[str] = Field("ja", description="字幕言語")
    webhook_url: Optional[HttpUrl] = Field(None, description="完了通知URL")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "quality": "720p",
                "audio_only": False,
                "subtitles": True,
                "subtitle_lang": "ja"
            }
        }
    }

class JobResponse(BaseModel):
    """ジョブレスポンス"""
    job_id: str = Field(..., description="ジョブID")
    status: JobStatus = Field(..., description="ジョブステータス")
    created_at: datetime = Field(..., description="作成日時")
    message: Optional[str] = Field(None, description="メッセージ")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "pending",
                "created_at": "2024-01-01T12:00:00Z",
                "message": "ジョブがキューに追加されました"
            }
        }
    }

class JobResult(BaseModel):
    """ジョブ結果"""
    job_id: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: Optional[float] = Field(None, ge=0, le=100)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    download_url: Optional[str] = None
    file_info: Optional[Dict[str, Any]] = None
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "success",
                "created_at": "2024-01-01T12:00:00Z",
                "started_at": "2024-01-01T12:00:05Z",
                "completed_at": "2024-01-01T12:02:30Z",
                "progress": 100.0,
                "download_url": "/api/job/550e8400-e29b-41d4-a716-446655440000/file",
                "file_info": {
                    "filename": "video.mp4",
                    "filesize": 52428800,
                    "duration": 180
                }
            }
        }
    }

class JobProgress(BaseModel):
    """ジョブ進捗情報"""
    downloaded_bytes: int = 0
    total_bytes: Optional[int] = None
    speed: Optional[float] = None
    eta: Optional[int] = None
    percentage: Optional[float] = None
