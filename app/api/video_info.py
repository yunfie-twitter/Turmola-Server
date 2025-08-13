from fastapi import APIRouter, HTTPException, Query, Request
import logging
from typing import Optional
import yt_dlp

from ..models.server import VideoInfo
from ..utils.rate_limiter import smart_rate_limit
from ..utils.helpers import sanitize_url
from ..services.cache_service import CacheService
from ..core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/info", response_model=VideoInfo)
@smart_rate_limit("30/minute")
async def get_video_info(
    request: Request,
    url: str = Query(..., description="動画URL"),
    use_cache: bool = Query(True, description="キャッシュを使用するか")
):
    """動画情報を取得（非同期処理なし）"""
    
    try:
        # URL正規化
        clean_url = sanitize_url(url)
        
        # キャッシュ確認
        cache_service = CacheService()
        cache_key = f"video_info:{hash(clean_url)}"
        
        if use_cache:
            cached_info = await cache_service.get(cache_key)
            if cached_info:
                logger.info(f"動画情報キャッシュヒット: {clean_url}")
                return VideoInfo(**cached_info)
        
        # yt-dlpで動画情報取得
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(clean_url, download=False)
                if not info:
                    raise HTTPException(
                        status_code=404,
                        detail="動画情報を取得できませんでした"
                    )
                
                # フォーマット情報処理
                formats = []
                if 'formats' in info and info['formats']:
                    for fmt in info['formats'][:10]:  # 最初の10個のみ
                        if fmt.get('vcodec') != 'none' and fmt.get('acodec') != 'none':
                            formats.append({
                                "format_id": fmt.get('format_id', ''),
                                "ext": fmt.get('ext', ''),
                                "resolution": fmt.get('resolution') or f"{fmt.get('width', 0)}x{fmt.get('height', 0)}",
                                "fps": fmt.get('fps'),
                                "vcodec": fmt.get('vcodec'),
                                "acodec": fmt.get('acodec'),
                                "filesize": fmt.get('filesize')
                            })
                
                # VideoInfoオブジェクト作成
                video_info = VideoInfo(
                    title=info.get('title', 'Unknown Title'),
                    duration=info.get('duration'),
                    uploader=info.get('uploader') or info.get('channel', 'Unknown'),
                    view_count=info.get('view_count'),
                    upload_date=info.get('upload_date'),
                    description=info.get('description', '')[:500] if info.get('description') else None,  # 500文字制限
                    thumbnail=info.get('thumbnail'),
                    formats=formats
                )
                
                # キャッシュに保存（1時間）
                if use_cache:
                    await cache_service.set(
                        cache_key,
                        video_info.model_dump(),
                        expire=3600
                    )
                
                logger.info(f"動画情報取得成功: {info.get('title', 'Unknown')}")
                return video_info
                
            except yt_dlp.DownloadError as e:
                logger.error(f"yt-dlp取得エラー: {e}")
                if "Video unavailable" in str(e):
                    raise HTTPException(
                        status_code=404,
                        detail="動画が見つからないか、アクセスできません"
                    )
                elif "Private video" in str(e):
                    raise HTTPException(
                        status_code=403,
                        detail="プライベート動画のため、アクセスできません"
                    )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"動画情報取得エラー: {str(e)}"
                    )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"動画情報取得エラー: {e}")
        raise HTTPException(
            status_code=500,
            detail="動画情報取得中にエラーが発生しました"
        )

@router.get("/info/formats")
@smart_rate_limit("20/minute")
async def get_video_formats(
    request: Request,
    url: str = Query(..., description="動画URL"),
    video_only: bool = Query(False, description="動画のみのフォーマット"),
    audio_only: bool = Query(False, description="音声のみのフォーマット")
):
    """動画の利用可能フォーマット一覧を取得"""
    
    try:
        clean_url = sanitize_url(url)
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'listformats': True,
            'skip_download': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            
            if not info or 'formats' not in info:
                raise HTTPException(
                    status_code=404,
                    detail="フォーマット情報を取得できませんでした"
                )
            
            formats = []
            for fmt in info['formats']:
                # フィルタリング
                if video_only and fmt.get('vcodec') == 'none':
                    continue
                if audio_only and fmt.get('acodec') == 'none':
                    continue
                
                format_info = {
                    "format_id": fmt.get('format_id', ''),
                    "ext": fmt.get('ext', ''),
                    "resolution": fmt.get('resolution'),
                    "fps": fmt.get('fps'),
                    "vcodec": fmt.get('vcodec', 'none'),
                    "acodec": fmt.get('acodec', 'none'),
                    "filesize": fmt.get('filesize'),
                    "tbr": fmt.get('tbr'),  # 総ビットレート
                    "format_note": fmt.get('format_note', ''),
                    "quality": fmt.get('quality')
                }
                formats.append(format_info)
            
            return {
                "title": info.get('title', 'Unknown'),
                "duration": info.get('duration'),
                "formats": formats,
                "total_formats": len(formats)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"フォーマット取得エラー: {e}")
        raise HTTPException(
            status_code=500,
            detail="フォーマット情報取得中にエラーが発生しました"
        )

@router.get("/info/thumbnail")
@smart_rate_limit("50/minute")
async def get_video_thumbnail(
    request: Request,
    url: str = Query(..., description="動画URL")
):
    """動画サムネイルURLを取得"""
    
    try:
        clean_url = sanitize_url(url)
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            
            if not info:
                raise HTTPException(
                    status_code=404,
                    detail="動画が見つかりません"
                )
            
            thumbnails = info.get('thumbnails', [])
            if not thumbnails:
                raise HTTPException(
                    status_code=404,
                    detail="サムネイルが見つかりません"
                )
            
            # 最高画質のサムネイルを選択
            best_thumbnail = max(thumbnails, key=lambda x: x.get('width', 0) * x.get('height', 0))
            
            return {
                "title": info.get('title', 'Unknown'),
                "thumbnail_url": best_thumbnail.get('url'),
                "width": best_thumbnail.get('width'),
                "height": best_thumbnail.get('height'),
                "all_thumbnails": thumbnails[:5]  # 最初の5個のサムネイル
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"サムネイル取得エラー: {e}")
        raise HTTPException(
            status_code=500,
            detail="サムネイル取得中にエラーが発生しました"
        )
