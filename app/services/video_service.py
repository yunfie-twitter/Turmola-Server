import yt_dlp
import asyncio
import logging
from typing import Optional, Dict, Any, List
from ..models.server import VideoInfo
from ..utils.helpers import sanitize_filename

logger = logging.getLogger(__name__)

class VideoService:
    """動画情報取得・処理サービス"""
    
    def __init__(self):
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extractaudio': False,
            'format': 'best',
            'ignoreerrors': True,
        }
    
    async def get_video_info(self, url: str) -> Optional[VideoInfo]:
        """動画情報を取得"""
        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None, self._extract_info, url
            )
            
            if not info:
                return None
            
            # フォーマット情報の整理
            formats = []
            if 'formats' in info:
                for fmt in info['formats']:
                    if fmt.get('vcodec') != 'none':  # 動画フォーマットのみ
                        formats.append({
                            'format_id': fmt.get('format_id'),
                            'ext': fmt.get('ext'),
                            'resolution': fmt.get('resolution') or f"{fmt.get('width', 'unknown')}x{fmt.get('height', 'unknown')}",
                            'fps': fmt.get('fps'),
                            'vcodec': fmt.get('vcodec'),
                            'acodec': fmt.get('acodec'),
                            'filesize': fmt.get('filesize')
                        })
            
            return VideoInfo(
                title=info.get('title', 'Unknown'),
                duration=info.get('duration'),
                uploader=info.get('uploader'),
                view_count=info.get('view_count'),
                upload_date=info.get('upload_date'),
                description=info.get('description', '')[:500] if info.get('description') else None,
                thumbnail=info.get('thumbnail'),
                formats=formats
            )
            
        except Exception as e:
            logger.error(f"動画情報取得エラー: {e}")
            return None
    
    def _extract_info(self, url: str) -> Optional[Dict[str, Any]]:
        """yt-dlpで動画情報抽出"""
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as e:
            logger.error(f"yt-dlp情報抽出エラー: {e}")
            return None
    
    async def get_available_formats(self, url: str) -> List[Dict[str, Any]]:
        """利用可能なフォーマット一覧を取得"""
        try:
            info = await self.get_video_info(url)
            if info:
                return info.formats
            return []
        except Exception as e:
            logger.error(f"フォーマット取得エラー: {e}")
            return []
    
    def get_download_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """ダウンロードオプションを生成"""
        ydl_opts = self.ydl_opts.copy()
        
        # 品質設定
        if options.get('audio_only'):
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['extractaudio'] = True
            ydl_opts['audioformat'] = 'mp3'
        else:
            quality = options.get('quality', 'best')
            if quality == 'best':
                ydl_opts['format'] = 'best'
            elif quality == 'worst':
                ydl_opts['format'] = 'worst'
            else:
                # 特定品質指定（720p等）
                ydl_opts['format'] = f'best[height<={quality.replace("p", "")}]'
        
        # フォーマットID指定
        if options.get('format_id'):
            ydl_opts['format'] = options['format_id']
        
        # 字幕設定
        if options.get('subtitles'):
            ydl_opts['writesubtitles'] = True
            ydl_opts['subtitleslangs'] = [options.get('subtitle_lang', 'ja')]
        
        # ファイル名テンプレート
        ydl_opts['outtmpl'] = '%(title)s.%(ext)s'
        
        return ydl_opts
