from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class ServerInfo(BaseModel):
    """サーバー情報"""
    server_type: str = Field(..., description="サーバー種別")
    yt_dlp_version: str = Field(..., description="yt-dlpバージョン")
    os_version: str = Field(..., description="OSバージョン")
    python_version: str = Field(..., description="Pythonバージョン")
    pending_jobs: int = Field(..., description="待機中ジョブ数")
    running_jobs: int = Field(..., description="実行中ジョブ数")
    max_concurrent_jobs: int = Field(..., description="最大同時実行ジョブ数")
    uptime: float = Field(..., description="稼働時間（秒）")
    memory_usage: Dict[str, Any] = Field(..., description="メモリ使用量")
    disk_usage: Dict[str, Any] = Field(..., description="ディスク使用量")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "server_type": "Premium",
                "yt_dlp_version": "2023.12.30",
                "os_version": "Ubuntu 22.04",
                "python_version": "3.10.12",
                "pending_jobs": 5,
                "running_jobs": 3,
                "max_concurrent_jobs": 10,
                "uptime": 86400.0,
                "memory_usage": {
                    "used": 2048,
                    "available": 6144,
                    "percent": 25.0
                },
                "disk_usage": {
                    "used": 10240,
                    "free": 51200,
                    "percent": 16.7
                }
            }
        }
    }

class VideoInfo(BaseModel):
    """動画情報"""
    title: str = Field(..., description="タイトル")
    duration: Optional[int] = Field(None, description="再生時間（秒）")
    uploader: Optional[str] = Field(None, description="アップローダー")
    view_count: Optional[int] = Field(None, description="再生回数")
    upload_date: Optional[str] = Field(None, description="アップロード日")
    description: Optional[str] = Field(None, description="説明")
    thumbnail: Optional[str] = Field(None, description="サムネイルURL")
    formats: List[Dict[str, Any]] = Field(..., description="利用可能フォーマット")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Sample Video",
                "duration": 180,
                "uploader": "Sample Channel",
                "view_count": 1000000,
                "upload_date": "20240101",
                "thumbnail": "https://example.com/thumb.jpg",
                "formats": [
                    {
                        "format_id": "22",
                        "ext": "mp4",
                        "resolution": "720p",
                        "filesize": 52428800
                    }
                ]
            }
        }
    }

class LogEntry(BaseModel):
    """ログエントリ"""
    timestamp: datetime
    level: str
    message: str
    job_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None
