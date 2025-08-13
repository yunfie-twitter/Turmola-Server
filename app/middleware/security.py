"""
セキュリティミドルウェア[10]
"""

import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from typing import Dict, Set
import asyncio

from ..utils.logging import get_security_logger
from ..utils.helpers import get_client_ip

logger = logging.getLogger(__name__)
security_logger = get_security_logger()

class SecurityMiddleware(BaseHTTPMiddleware):
    """セキュリティミドルウェア"""
    
    def __init__(self, app):
        super().__init__(app)
        
        # ブロックされたIP
        self.blocked_ips: Set[str] = set()
        
        # 不審なアクセス追跡
        self.suspicious_attempts: Dict[str, list] = {}
        
        # 許可されたUser-Agent パターン
        self.allowed_user_agents = {
            'python-requests', 'curl', 'wget', 'httpx', 'aiohttp',
            'mozilla', 'chrome', 'firefox', 'safari', 'edge'
        }
        
        # 不審なパスパターン
        self.suspicious_paths = {
            '/wp-admin', '/admin', '/.env', '/config', '/backup',
            '/phpmyadmin', '/mysql', '/database', '/.git',
            '/shell', '/cmd', '/execute', '/eval'
        }
    
    async def dispatch(self, request: Request, call_next):
        """リクエスト処理"""
        
        client_ip = get_client_ip(request)
        user_agent = request.headers.get("user-agent", "").lower()
        path = request.url.path
        
        # ブロック済みIPチェック
        if client_ip in self.blocked_ips:
            security_logger.log_blocked_request(client_ip, "Blocked IP")
            return JSONResponse(
                status_code=403,
                content={"error": "アクセスが拒否されました"}
            )
        
        # 不審なパスアクセスチェック
        if any(suspicious in path for suspicious in self.suspicious_paths):
            security_logger.log_suspicious_access(
                client_ip, user_agent, path, "Suspicious path access"
            )
            await self._record_suspicious_attempt(client_ip)
            return JSONResponse(
                status_code=404,
                content={"error": "ページが見つかりません"}
            )
        
        # 不審なUser-Agentチェック
        if not any(allowed in user_agent for allowed in self.allowed_user_agents) and user_agent:
            security_logger.log_suspicious_access(
                client_ip, user_agent, path, "Suspicious User-Agent"
            )
            await self._record_suspicious_attempt(client_ip)
        
        # SQLインジェクション試行チェック
        query_string = str(request.url.query)
        sql_patterns = ['union select', 'drop table', 'insert into', '1=1', '1\'=\'1']
        if any(pattern in query_string.lower() for pattern in sql_patterns):
            security_logger.log_suspicious_access(
                client_ip, user_agent, path, "SQL injection attempt"
            )
            await self._record_suspicious_attempt(client_ip)
            return JSONResponse(
                status_code=400,
                content={"error": "不正なリクエストです"}
            )
        
        # リクエスト処理時間計測
        start_time = time.time()
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # レスポンスヘッダー追加
            response.headers["X-Process-Time"] = str(process_time)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            
            return response
            
        except Exception as e:
            logger.error(f"リクエスト処理エラー: {e}")
            return JSONResponse(
                status_code=500,
                content={"error": "内部サーバーエラー"}
            )
    
    async def _record_suspicious_attempt(self, ip: str):
        """不審なアクセスを記録"""
        current_time = time.time()
        
        if ip not in self.suspicious_attempts:
            self.suspicious_attempts[ip] = []
        
        # 1時間以内の試行を記録
        self.suspicious_attempts[ip] = [
            attempt for attempt in self.suspicious_attempts[ip]
            if current_time - attempt < 3600
        ]
        
        self.suspicious_attempts[ip].append(current_time)
        
        # 1時間に5回以上の不審なアクセスでブロック
        if len(self.suspicious_attempts[ip]) >= 5:
            self.blocked_ips.add(ip)
            security_logger.log_blocked_request(
                ip, f"Multiple suspicious attempts: {len(self.suspicious_attempts[ip])}"
            )
            
            # 24時間後に自動解除
            asyncio.create_task(self._unblock_ip_after_delay(ip, 86400))
    
    async def _unblock_ip_after_delay(self, ip: str, delay: int):
        """指定時間後にIPブロックを解除"""
        await asyncio.sleep(delay)
        if ip in self.blocked_ips:
            self.blocked_ips.remove(ip)
            logger.info(f"IPブロック自動解除: {ip}")
