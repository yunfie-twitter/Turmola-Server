"""
ダウンロード高速化サービス（完全版）
"""

import os
import asyncio
import logging
import tempfile
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import yt_dlp

logger = logging.getLogger(__name__)

class DownloadAccelerator:
    """ダウンロード高速化管理（完全版）"""
    
    def __init__(self):
        """初期化処理"""
        # 設定の安全な読み込み
        self._load_settings()
        
        # aria2サービスの遅延初期化
        self._aria2_service = None
        self._aria2_initialized = False
        
        # スレッドプール初期化
        self._thread_pool = ThreadPoolExecutor(max_workers=4)
        
        logger.info(f"DownloadAccelerator初期化完了 - aria2有効: {self.aria2_enabled}")
    
    def _load_settings(self):
        """設定の安全な読み込み"""
        try:
            from ..core.config import settings
            self.aria2_enabled = getattr(settings, 'ENABLE_ARIA2', False)
            self.aria2_threshold_mb = getattr(settings, 'ARIA2_THRESHOLD_MB', 50)
            self.max_connections = getattr(settings, 'ARIA2_MAX_CONNECTIONS', 10)
            self.max_splits = getattr(settings, 'ARIA2_SPLITS', 10)
            self.storage_path = getattr(settings, 'STORAGE_PATH', '/app/downloads')
            logger.debug("設定読み込み完了")
        except ImportError:
            # settings が利用できない場合のデフォルト値
            self.aria2_enabled = os.getenv('ENABLE_ARIA2', 'false').lower() == 'true'
            self.aria2_threshold_mb = int(os.getenv('ARIA2_THRESHOLD_MB', '50'))
            self.max_connections = int(os.getenv('ARIA2_MAX_CONNECTIONS', '10'))
            self.max_splits = int(os.getenv('ARIA2_SPLITS', '10'))
            self.storage_path = os.getenv('STORAGE_PATH', '/app/downloads')
            logger.warning("設定をデフォルト値で初期化")
    
    def _get_aria2_service(self):
        """aria2サービスの遅延初期化"""
        if not self._aria2_initialized:
            try:
                from ..services.aria2_service import aria2_service
                self._aria2_service = aria2_service
                self._aria2_initialized = True
                logger.debug("aria2サービス初期化完了")
            except ImportError as e:
                logger.warning(f"aria2サービス初期化失敗: {e}")
                self._aria2_service = None
                self._aria2_initialized = True
        
        return self._aria2_service
    
    def enhanced_download_sync(
        self,
        url: str,
        video_info: Dict[str, Any],
        output_path: str,
        options: Dict[str, Any] = None,
        progress_callback: callable = None
    ) -> Dict[str, Any]:
        """
        強化されたダウンロード処理（同期版）
        
        Args:
            url: ダウンロードURL
            video_info: 動画情報（yt-dlpから取得）
            output_path: 出力パス
            options: ダウンロードオプション
            progress_callback: 進捗コールバック
            
        Returns:
            ダウンロード結果辞書
        """
        options = options or {}
        
        try:
            logger.info(f"強化ダウンロード開始: {url}")
            
            # 新しいイベントループで非同期版を実行
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(
                    self.enhanced_download(
                        url, video_info, output_path, options, progress_callback
                    )
                )
                logger.info(f"強化ダウンロード完了: method={result.get('method')}")
                return result
                
            finally:
                # イベントループのクリーンアップ
                try:
                    # 残っているタスクをキャンセル
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    
                    loop.close()
                except Exception as cleanup_error:
                    logger.warning(f"イベントループクリーンアップ警告: {cleanup_error}")
            
        except Exception as e:
            logger.error(f"同期強化ダウンロードエラー: {e}")
            return {
                "status": "fallback_to_ytdlp",
                "error": str(e),
                "method": "sync_error"
            }
    
    async def enhanced_download(
        self,
        url: str,
        video_info: Dict[str, Any],
        output_path: str,
        options: Dict[str, Any] = None,
        progress_callback: callable = None
    ) -> Dict[str, Any]:
        """
        強化されたダウンロード処理（非同期版）
        
        Args:
            url: ダウンロードURL
            video_info: 動画情報（yt-dlpから取得）
            output_path: 出力パス
            options: ダウンロードオプション
            progress_callback: 進捗コールバック
            
        Returns:
            ダウンロード結果辞書
        """
        options = options or {}
        
        try:
            # ダウンロード方法の判定
            download_method = await self._determine_download_method(video_info, options)
            
            logger.info(f"ダウンロード方法選択: {download_method} for {url}")
            
            if download_method == "aria2" and self.aria2_enabled:
                return await self._download_with_aria2(
                    url, video_info, output_path, options, progress_callback
                )
            elif download_method == "segmented":
                return await self._download_segmented(
                    url, video_info, output_path, options, progress_callback
                )
            elif download_method == "parallel":
                return await self._download_parallel(
                    url, video_info, output_path, options, progress_callback
                )
            else:
                return {
                    "status": "fallback_to_ytdlp",
                    "method": download_method,
                    "reason": "No enhanced method available"
                }
                
        except Exception as e:
            logger.error(f"非同期強化ダウンロードエラー: {e}")
            return {
                "status": "fallback_to_ytdlp",
                "error": str(e),
                "method": "async_error"
            }
    
    async def _determine_download_method(
        self,
        video_info: Dict[str, Any],
        options: Dict[str, Any]
    ) -> str:
        """最適なダウンロード方法を判定"""
        
        try:
            # ユーザー指定があればそれを優先
            if options.get('force_aria2') and self.aria2_enabled:
                logger.debug("強制aria2モード")
                return "aria2"
            elif options.get('force_standard'):
                logger.debug("強制標準モード")
                return "standard"
            elif options.get('force_parallel'):
                logger.debug("強制並列モード")
                return "parallel"
            
            # aria2が無効の場合
            if not self.aria2_enabled:
                logger.debug("aria2無効のため標準モードを選択")
                return "standard"
            
            # ファイルサイズ基準
            filesize = video_info.get('filesize') or video_info.get('filesize_approx', 0)
            
            if filesize and filesize > self.aria2_threshold_mb * 1024 * 1024:
                # aria2の状態確認
                aria2_service = self._get_aria2_service()
                if aria2_service:
                    try:
                        if await aria2_service.check_aria2_status():
                            logger.debug(f"ファイルサイズ基準でaria2選択: {filesize} bytes")
                            return "aria2"
                        else:
                            logger.warning("aria2が応答しないため並列ダウンロードに変更")
                            return "parallel"
                    except Exception as e:
                        logger.warning(f"aria2ステータス確認エラー: {e}")
                
            # フォーマット基準
            formats = video_info.get('formats', [])
            if formats:
                # HLS形式の場合はセグメント化ダウンロード
                for fmt in formats:
                    if fmt.get('protocol') in ['m3u8', 'hls', 'm3u8_native']:
                        logger.debug("HLS形式のためセグメント化ダウンロード選択")
                        return "segmented"
                    
                    # DASH形式の場合は並列ダウンロード
                    if fmt.get('protocol') in ['http_dash_segments']:
                        logger.debug("DASH形式のため並列ダウンロード選択")
                        return "parallel"
            
            # 動画の長さ基準
            duration = video_info.get('duration', 0)
            if duration and duration > 1800:  # 30分以上
                logger.debug(f"長時間動画のため並列ダウンロード選択: {duration}秒")
                return "parallel"
            
            logger.debug("標準ダウンロード選択")
            return "standard"
            
        except Exception as e:
            logger.warning(f"ダウンロード方法判定エラー: {e}")
            return "standard"
    
    async def _download_with_aria2(
        self,
        url: str,
        video_info: Dict[str, Any],
        output_path: str,
        options: Dict[str, Any],
        progress_callback: callable
    ) -> Dict[str, Any]:
        """aria2 による高速ダウンロード"""
        
        try:
            aria2_service = self._get_aria2_service()
            if not aria2_service:
                raise Exception("aria2サービスが利用できません")
            
            logger.info("aria2ダウンロード開始")
            
            # ダウンロードファイル名
            title = video_info.get('title', 'video')
            ext = video_info.get('ext', 'mp4')
            
            from ..utils.helpers import sanitize_filename
            filename = f"{sanitize_filename(title)}.{ext}"
            
            # aria2 オプション設定
            aria2_options = {
                'max_connections': options.get('aria2_connections', self.max_connections),
                'split_parts': options.get('aria2_splits', self.max_splits),
                'continue': True,
                'allow_overwrite': False
            }
            
            # ダウンロード開始
            gid = await aria2_service.download_with_aria2(
                url, filename, aria2_options
            )
            
            if not gid:
                raise Exception("aria2ダウンロード開始に失敗")
            
            # 進捗監視
            def aria2_progress_callback(status):
                if progress_callback:
                    progress_callback({
                        'status': 'downloading',
                        'progress': status.get('progress', 0),
                        'speed': status.get('download_speed', '0'),
                        'method': 'aria2',
                        'connections': status.get('num_connections', '0')
                    })
            
            # 完了待ち
            result = await aria2_service.wait_for_completion(
                gid, 
                timeout=3600,
                progress_callback=aria2_progress_callback
            )
            
            if result['status'] == 'success':
                # ファイル情報取得
                downloaded_files = []
                if result.get('files'):
                    for file_info in result['files']:
                        file_path = file_info.get('path', '')
                        if os.path.exists(file_path):
                            downloaded_files.append(os.path.basename(file_path))
                
                logger.info(f"aria2ダウンロード完了: {len(downloaded_files)}ファイル")
                
                return {
                    "status": "success",
                    "method": "aria2",
                    "files": downloaded_files,
                    "gid": gid,
                    "download_time": result.get('download_time'),
                    "average_speed": result.get('average_speed')
                }
            else:
                return {
                    "status": "failed",
                    "method": "aria2",
                    "error": result.get('message', 'aria2 download failed'),
                    "gid": gid
                }
                
        except Exception as e:
            logger.error(f"aria2ダウンロードエラー: {e}")
            return {
                "status": "fallback_to_ytdlp",
                "method": "aria2",
                "error": str(e)
            }
    
    async def _download_segmented(
        self,
        url: str,
        video_info: Dict[str, Any],
        output_path: str,
        options: Dict[str, Any],
        progress_callback: callable
    ) -> Dict[str, Any]:
        """セグメント化ダウンロード（HLS等）"""
        
        try:
            logger.info("セグメント化ダウンロード開始")
            
            # HLSセグメント用の特別処理
            ydl_opts = {
                'format': 'best',
                'noplaylist': True,
                'extract_flat': False,
                'writeinfojson': False,
                'quiet': False,
                'no_warnings': False,
                
                # セグメント並列ダウンロード設定
                'concurrent_fragment_downloads': options.get('concurrent_segments', 4),
                'fragment_retries': 5,
                'skip_unavailable_fragments': True,
                
                # HLS特有設定
                'hls_prefer_native': True,
                'hls_use_mpegts': False,
                
                # 出力設定
                'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                'restrictfilenames': False,
            }
            
            def segment_progress_hook(d):
                if d['status'] == 'downloading' and progress_callback:
                    progress = 0
                    if 'total_bytes' in d and d['total_bytes']:
                        progress = (d['downloaded_bytes'] / d['total_bytes']) * 100
                    elif '_percent_str' in d:
                        try:
                            progress = float(d['_percent_str'].strip('%'))
                        except:
                            progress = 0
                    
                    progress_callback({
                        'status': 'downloading',
                        'progress': progress,
                        'method': 'segmented',
                        'fragments': d.get('fragment_index', 0),
                        'total_fragments': d.get('fragment_count', 0)
                    })
            
            ydl_opts['progress_hooks'] = [segment_progress_hook]
            
            # 非同期でyt-dlpを実行
            loop = asyncio.get_event_loop()
            
            def run_ytdlp():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            
            await loop.run_in_executor(self._thread_pool, run_ytdlp)
            
            # ダウンロード完了ファイル検索
            downloaded_files = []
            if os.path.exists(output_path):
                for file in os.listdir(output_path):
                    file_path = os.path.join(output_path, file)
                    if os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
                        downloaded_files.append(file)
            
            if downloaded_files:
                logger.info(f"セグメント化ダウンロード完了: {len(downloaded_files)}ファイル")
                
                return {
                    "status": "success",
                    "method": "segmented",
                    "files": downloaded_files
                }
            else:
                return {
                    "status": "fallback_to_ytdlp",
                    "method": "segmented",
                    "error": "No files downloaded"
                }
            
        except Exception as e:
            logger.error(f"セグメント化ダウンロードエラー: {e}")
            return {
                "status": "fallback_to_ytdlp",
                "method": "segmented",
                "error": str(e)
            }
    
    async def _download_parallel(
        self,
        url: str,
        video_info: Dict[str, Any],
        output_path: str,
        options: Dict[str, Any],
        progress_callback: callable
    ) -> Dict[str, Any]:
        """並列ダウンロード（HTTPレンジリクエスト）"""
        
        try:
            logger.info("並列ダウンロード開始")
            
            # 並列ダウンロード用の特別処理
            ydl_opts = {
                'format': 'best',
                'noplaylist': True,
                'extract_flat': False,
                'writeinfojson': False,
                'quiet': False,
                
                # HTTPオプション
                'http_chunk_size': 10485760,  # 10MB
                'retries': 5,
                'fragment_retries': 5,
                
                # 並列設定
                'concurrent_fragment_downloads': options.get('parallel_connections', 4),
                
                # 出力設定
                'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                'restrictfilenames': False,
            }
            
            def parallel_progress_hook(d):
                if d['status'] == 'downloading' and progress_callback:
                    progress = 0
                    if 'total_bytes' in d and d['total_bytes']:
                        progress = (d['downloaded_bytes'] / d['total_bytes']) * 100
                    elif '_percent_str' in d:
                        try:
                            progress = float(d['_percent_str'].strip('%'))
                        except:
                            progress = 0
                    
                    progress_callback({
                        'status': 'downloading',
                        'progress': progress,
                        'method': 'parallel',
                        'speed': d.get('speed', 0)
                    })
            
            ydl_opts['progress_hooks'] = [parallel_progress_hook]
            
            # 非同期でyt-dlpを実行
            loop = asyncio.get_event_loop()
            
            def run_ytdlp():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            
            await loop.run_in_executor(self._thread_pool, run_ytdlp)
            
            # ダウンロード完了ファイル検索
            downloaded_files = []
            if os.path.exists(output_path):
                for file in os.listdir(output_path):
                    file_path = os.path.join(output_path, file)
                    if os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
                        downloaded_files.append(file)
            
            if downloaded_files:
                logger.info(f"並列ダウンロード完了: {len(downloaded_files)}ファイル")
                
                return {
                    "status": "success",
                    "method": "parallel",
                    "files": downloaded_files
                }
            else:
                return {
                    "status": "fallback_to_ytdlp",
                    "method": "parallel",
                    "error": "No files downloaded"
                }
            
        except Exception as e:
            logger.error(f"並列ダウンロードエラー: {e}")
            return {
                "status": "fallback_to_ytdlp",
                "method": "parallel",
                "error": str(e)
            }
    
    def get_download_stats(self) -> Dict[str, Any]:
        """ダウンロード統計取得"""
        try:
            aria2_service = self._get_aria2_service()
            aria2_stats = {}
            
            if aria2_service and self.aria2_enabled:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    aria2_stats = loop.run_until_complete(
                        aria2_service.get_global_stats()
                    )
                finally:
                    loop.close()
            
            return {
                "aria2_enabled": self.aria2_enabled,
                "aria2_stats": aria2_stats,
                "threshold_mb": self.aria2_threshold_mb,
                "max_connections": self.max_connections,
                "max_splits": self.max_splits
            }
            
        except Exception as e:
            logger.error(f"ダウンロード統計取得エラー: {e}")
            return {"error": str(e)}
    
    def __del__(self):
        """デストラクタ"""
        try:
            if hasattr(self, '_thread_pool'):
                self._thread_pool.shutdown(wait=False)
        except:
            pass

# グローバルダウンロード高速化サービス（安全な初期化）
try:
    download_accelerator = DownloadAccelerator()
    logger.info("DownloadAccelerator グローバルインスタンス作成完了")
except Exception as e:
    logger.error(f"DownloadAccelerator 初期化エラー: {e}")
    download_accelerator = None
