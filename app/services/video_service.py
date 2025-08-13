"""
動画サービス（YouTube判別対応版）
"""

import os
import re
from typing import Dict, Any
from urllib.parse import urlparse

class VideoService:
    """動画ダウンロード設定サービス"""
    
    @staticmethod
    def is_youtube_url(url: str) -> bool:
        """YouTubeのURLかどうか判定"""
        youtube_patterns = [
            r'(?:youtube\.com|youtu\.be)',
            r'(?:www\.youtube\.com)',
            r'(?:m\.youtube\.com)',
            r'(?:music\.youtube\.com)',
        ]
        
        for pattern in youtube_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False
    
    def get_download_options(self, options: Dict[str, Any], url: str = "") -> Dict[str, Any]:
        """yt-dlpダウンロードオプション生成（YouTube判別対応版）"""
        
        is_youtube = self.is_youtube_url(url)
        
        if is_youtube:
            return self._get_youtube_options(options)
        else:
            return self._get_other_site_options(options)
    
    def _get_youtube_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """YouTube用ダウンロードオプション（従来版）"""
        
        ydl_opts = {
            # 基本設定
            'format': self._get_youtube_format_selector(options),
            'noplaylist': True,
            'no_warnings': False,
            'quiet': False,
            
            # 動画を確実にダウンロードする設定
            'skip_download': False,
            'extract_flat': False,
            
            # 出力設定
            'outtmpl': '%(title)s.%(ext)s',
            'restrictfilenames': True,
            
            # 品質設定
            'merge_output_format': 'mp4',
            'writeinfojson': False,
            
            # 字幕設定（条件付き）
            'writesubtitles': options.get('subtitles', False),
            'writeautomaticsub': options.get('subtitles', False),
            'subtitleslangs': [options.get('subtitle_lang', 'ja')] if options.get('subtitles') else [],
            'embed_subs': False,
            
            # エラー処理
            'ignoreerrors': False,
            'retries': 3,
            'fragment_retries': 3,
            'skip_unavailable_fragments': False,
        }
        
        return ydl_opts
    
    def _get_other_site_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """YouTube以外のサイト用ダウンロードオプション（例外処理強化版）"""
        
        ydl_opts = {
            # 基本設定（より柔軟に）
            'format': self._get_flexible_format_selector(options),
            'noplaylist': True,
            'no_warnings': False,
            'quiet': False,
            
            # 動画を確実にダウンロードする設定
            'skip_download': False,
            'extract_flat': False,
            
            # 出力設定
            'outtmpl': '%(title)s.%(ext)s',
            'restrictfilenames': True,
            
            # 品質設定（より寛容に）
            'merge_output_format': 'mp4',
            'writeinfojson': False,
            
            # 字幕設定（YouTube以外では控えめに）
            'writesubtitles': options.get('subtitles', False),
            'writeautomaticsub': False,  # 自動字幕は無効
            'subtitleslangs': [options.get('subtitle_lang', 'ja')] if options.get('subtitles') else [],
            'embed_subs': False,
            
            # エラー処理（より寛容に）
            'ignoreerrors': True,  # 一部エラーを無視
            'retries': 5,  # リトライ回数を増加
            'fragment_retries': 5,
            'skip_unavailable_fragments': True,  # 利用できないフラグメントをスキップ
            
            # ニコニコ動画等の固有設定
            'http_chunk_size': 10485760,  # 10MB
            'extractor_retries': 3,
        }
        
        return ydl_opts
    
    def _get_youtube_format_selector(self, options: Dict[str, Any]) -> str:
        """YouTubeフォーマット選択（従来版）"""
        
        quality = options.get('quality', 'best')
        audio_only = options.get('audio_only', False)
        format_id = options.get('format_id')
        
        if format_id:
            return format_id
        
        if audio_only:
            return 'bestaudio/best'
        
        # YouTube用の詳細なフォーマット指定
        if quality == 'best':
            return 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        elif quality == 'worst':
            return 'worstvideo[ext=mp4]+worstaudio[ext=m4a]/worst[ext=mp4]/worst'
        elif quality.endswith('p'):
            height = quality[:-1]
            return f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={height}][ext=mp4]/best'
        else:
            return 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    
    def _get_flexible_format_selector(self, options: Dict[str, Any]) -> str:
        """柔軟なフォーマット選択（YouTube以外用）"""
        
        quality = options.get('quality', 'best')
        audio_only = options.get('audio_only', False)
        format_id = options.get('format_id')
        
        if format_id:
            return format_id
        
        if audio_only:
            # 音声のみ（より柔軟に）
            return 'bestaudio/worst'
        
        # 他サイト用の柔軟なフォーマット選択
        if quality == 'best':
            return 'best'  # シンプルに最高画質
        elif quality == 'worst':
            return 'worst'  # シンプルに最低画質
        elif quality.endswith('p'):
            # 品質指定があっても、利用できない場合はbestにフォールバック
            height = quality[:-1]
            return f'best[height<={height}]/best'
        else:
            return 'best'  # デフォルトは最高画質
