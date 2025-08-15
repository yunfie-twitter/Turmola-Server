"""
aria2 統合サービス（高速ダウンロード）
"""

import os
import json
import logging
import asyncio
import websockets
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime
import subprocess

from ..core.config import settings
from ..utils.helpers import sanitize_filename

logger = logging.getLogger(__name__)

class Aria2Service:
    """aria2 RPC クライアント"""
    
    def __init__(self):
        self.rpc_url = "http://localhost:6800/jsonrpc"
        self.rpc_secret = getattr(settings, 'ARIA2_SECRET', 'turmola_secret')
        self.download_dir = settings.STORAGE_PATH
        self.session_id = None
        
    async def start_aria2_daemon(self):
        """aria2 デーモン起動"""
        try:
            # aria2c デーモンモードで起動
            cmd = [
                "aria2c",
                "--enable-rpc",
                "--rpc-listen-all=true",
                "--rpc-listen-port=6800",
                f"--rpc-secret={self.rpc_secret}",
                f"--dir={self.download_dir}",
                "--max-concurrent-downloads=5",
                "--max-connection-per-server=10",
                "--split=10",
                "--min-split-size=1M",
                "--file-allocation=prealloc",
                "--continue=true",
                "--auto-file-renaming=false",
                "--daemon=true",
                "--log=/app/logs/aria2.log",
                "--log-level=info"
            ]
            
            process = subprocess.Popen(cmd, 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE)
            
            # 起動確認
            await asyncio.sleep(2)
            
            if await self.check_aria2_status():
                logger.info("aria2 daemon started successfully")
                return True
            else:
                logger.error("aria2 daemon failed to start")
                return False
                
        except Exception as e:
            logger.error(f"aria2 startup error: {e}")
            return False
    
    async def check_aria2_status(self) -> bool:
        """aria2 ステータス確認"""
        try:
            response = await self._rpc_call("aria2.getVersion")
            if response and "result" in response:
                version = response["result"]["version"]
                logger.debug(f"aria2 version: {version}")
                return True
            return False
        except Exception as e:
            logger.warning(f"aria2 status check failed: {e}")
            return False
    
    async def _rpc_call(self, method: str, params: List = None) -> Optional[Dict]:
        """aria2 RPC 呼び出し"""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": "turmola",
                "method": method,
                "params": [f"token:{self.rpc_secret}"] + (params or [])
            }
            
            async with asyncio.timeout(30):
                response = requests.post(
                    self.rpc_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"aria2 RPC error: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"aria2 RPC call error: {e}")
            return None
    
    async def download_with_aria2(
        self,
        url: str,
        filename: str = None,
        options: Dict[str, Any] = None
    ) -> Optional[str]:
        """aria2 でダウンロード実行"""
        try:
            # aria2 ダウンロードオプション
            aria2_options = {
                "max-connection-per-server": "10",
                "split": "10",
                "min-split-size": "1M",
                "continue": "true",
                "auto-file-renaming": "false"
            }
            
            # カスタムオプション適用
            if options:
                if options.get('max_connections'):
                    aria2_options["max-connection-per-server"] = str(options['max_connections'])
                if options.get('split_parts'):
                    aria2_options["split"] = str(options['split_parts'])
                if filename:
                    safe_filename = sanitize_filename(filename)
                    aria2_options["out"] = safe_filename
            
            # ダウンロード開始
            response = await self._rpc_call("aria2.addUri", [[url], aria2_options])
            
            if response and "result" in response:
                gid = response["result"]
                logger.info(f"aria2 download started: {gid} for {url}")
                return gid
            else:
                logger.error(f"aria2 download start failed: {response}")
                return None
                
        except Exception as e:
            logger.error(f"aria2 download error: {e}")
            return None
    
    async def get_download_status(self, gid: str) -> Optional[Dict[str, Any]]:
        """ダウンロードステータス取得"""
        try:
            response = await self._rpc_call("aria2.tellStatus", [gid])
            
            if response and "result" in response:
                status_data = response["result"]
                
                # ステータス変換
                aria2_status = status_data.get("status", "unknown")
                progress = 0
                
                if aria2_status == "complete":
                    progress = 100
                elif aria2_status == "active":
                    total_length = int(status_data.get("totalLength", 0))
                    completed_length = int(status_data.get("completedLength", 0))
                    
                    if total_length > 0:
                        progress = (completed_length / total_length) * 100
                
                return {
                    "gid": gid,
                    "status": aria2_status,
                    "progress": progress,
                    "download_speed": status_data.get("downloadSpeed", "0"),
                    "total_length": status_data.get("totalLength", "0"),
                    "completed_length": status_data.get("completedLength", "0"),
                    "num_connections": status_data.get("connections", "0"),
                    "files": status_data.get("files", [])
                }
            
            return None
            
        except Exception as e:
            logger.error(f"aria2 status check error: {e}")
            return None
    
    async def wait_for_completion(
        self,
        gid: str,
        timeout: int = 3600,
        progress_callback: callable = None
    ) -> Dict[str, Any]:
        """ダウンロード完了まで待機"""
        start_time = datetime.utcnow()
        last_progress = -1
        
        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            try:
                status = await self.get_download_status(gid)
                
                if not status:
                    return {"status": "error", "message": "Status check failed"}
                
                # 進捗コールバック
                if progress_callback and status["progress"] != last_progress:
                    progress_callback(status)
                    last_progress = status["progress"]
                
                # 完了チェック
                if status["status"] == "complete":
                    return {
                        "status": "success",
                        "files": status["files"],
                        "gid": gid
                    }
                elif status["status"] == "error":
                    return {
                        "status": "failed",
                        "message": "aria2 download error",
                        "gid": gid
                    }
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"aria2 wait error: {e}")
                return {"status": "error", "message": str(e)}
        
        # タイムアウト
        await self.cancel_download(gid)
        return {"status": "timeout", "message": "Download timeout"}
    
    async def cancel_download(self, gid: str) -> bool:
        """ダウンロードキャンセル"""
        try:
            response = await self._rpc_call("aria2.remove", [gid])
            return response and "result" in response
        except Exception as e:
            logger.error(f"aria2 cancel error: {e}")
            return False
    
    async def get_global_stats(self) -> Dict[str, Any]:
        """aria2 グローバル統計取得"""
        try:
            response = await self._rpc_call("aria2.getGlobalStat")
            
            if response and "result" in response:
                stats = response["result"]
                return {
                    "download_speed": stats.get("downloadSpeed", "0"),
                    "upload_speed": stats.get("uploadSpeed", "0"),
                    "num_active": stats.get("numActive", "0"),
                    "num_waiting": stats.get("numWaiting", "0"),
                    "num_stopped": stats.get("numStopped", "0"),
                    "num_stopped_total": stats.get("numStoppedTotal", "0")
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"aria2 stats error: {e}")
            return {}

# グローバルaria2サービス
aria2_service = Aria2Service()
