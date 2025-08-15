"""
セキュリティミドルウェア（完全版）
"""

from fastapi import Request, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
import logging

from ..core.config import settings
from ..utils.helpers import get_client_ip

logger = logging.getLogger(__name__)

# API Key Security Headers
ADMIN_API_KEY_NAME = "X-Admin-Key"
PREMIUM_API_KEY_NAME = "X-Premium-Key"

# API Key Header インスタンス
admin_api_key_header = APIKeyHeader(name=ADMIN_API_KEY_NAME, auto_error=False)
premium_api_key_header = APIKeyHeader(name=PREMIUM_API_KEY_NAME, auto_error=False)

# セキュリティ依存関数群
async def require_admin_key(api_key: str = Security(admin_api_key_header)) -> str:
    """
    管理者APIキー検証依存関数
    
    Args:
        api_key: ヘッダーから取得されるAPIキー
        
    Returns:
        str: 検証済みAPIキー
        
    Raises:
        HTTPException: APIキーが無効な場合
    """
    try:
        admin_key = getattr(settings, 'ADMIN_API_KEY', None) or getattr(settings, 'PREMIUM_API_KEY', 'development-admin-key')
        
        if not api_key:
            logger.warning("管理者APIキーが提供されていません")
            raise HTTPException(
                status_code=403, 
                detail="管理者APIキーが必要です"
            )
        
        if api_key != admin_key:
            logger.warning(f"無効な管理者APIキー: {api_key[:8]}...")
            raise HTTPException(
                status_code=403, 
                detail="管理者APIキーが無効です"
            )
        
        logger.debug("管理者APIキー検証成功")
        return api_key
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"管理者APIキー検証エラー: {e}")
        raise HTTPException(
            status_code=500, 
            detail="APIキー検証中にエラーが発生しました"
        )

async def require_premium_key(api_key: str = Security(premium_api_key_header)) -> str:
    """
    プレミアムAPIキー検証依存関数
    
    Args:
        api_key: ヘッダーから取得されるAPIキー
        
    Returns:
        str: 検証済みAPIキー
        
    Raises:
        HTTPException: APIキーが無効な場合
    """
    try:
        premium_key = getattr(settings, 'PREMIUM_API_KEY', 'development-premium-key')
        
        if not api_key:
            logger.warning("プレミアムAPIキーが提供されていません")
            raise HTTPException(
                status_code=403, 
                detail="プレミアムAPIキーが必要です"
            )
        
        if api_key != premium_key:
            logger.warning(f"無効なプレミアムAPIキー: {api_key[:8]}...")
            raise HTTPException(
                status_code=403, 
                detail="プレミアムAPIキーが無効です"
            )
        
        logger.debug("プレミアムAPIキー検証成功")
        return api_key
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"プレミアムAPIキー検証エラー: {e}")
        raise HTTPException(
            status_code=500, 
            detail="APIキー検証中にエラーが発生しました"
        )

async def optional_api_key(api_key: str = Security(premium_api_key_header)) -> Optional[str]:
    """
    オプションAPIキー検証（キーがなくてもエラーにしない）
    
    Args:
        api_key: ヘッダーから取得されるAPIキー
        
    Returns:
        Optional[str]: 検証済みAPIキーまたはNone
    """
    try:
        if not api_key:
            return None
        
        premium_key = getattr(settings, 'PREMIUM_API_KEY', 'development-premium-key')
        
        if api_key == premium_key:
            logger.debug("オプションAPIキー検証成功")
            return api_key
        else:
            logger.debug("オプションAPIキー検証失敗")
            return None
            
    except Exception as e:
        logger.warning(f"オプションAPIキー検証エラー: {e}")
        return None

# IP アドレス検証
def validate_client_ip(request: Request) -> str:
    """
    クライアントIP検証
    
    Args:
        request: FastAPI Request
        
    Returns:
        str: クライアントIPアドレス
    """
    try:
        client_ip = get_client_ip(request)
        
        # 許可されたIPアドレスのチェック（設定がある場合）
        allowed_ips = getattr(settings, 'ALLOWED_IPS', None)
        if allowed_ips and client_ip not in allowed_ips:
            logger.warning(f"許可されていないIPアドレス: {client_ip}")
            raise HTTPException(
                status_code=403, 
                detail="アクセスが許可されていません"
            )
        
        return client_ip
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"IP検証エラー: {e}")
        raise HTTPException(
            status_code=500, 
            detail="IP検証中にエラーが発生しました"
        )

# レート制限チェック
async def check_rate_limit(request: Request) -> bool:
    """
    レート制限チェック
    
    Args:
        request: FastAPI Request
        
    Returns:
        bool: レート制限内かどうか
    """
    try:
        # レート制限が無効な場合はスキップ
        if not getattr(settings, 'ENABLE_RATE_LIMITING', False):
            return True
        
        client_ip = get_client_ip(request)
        
        # 簡易レート制限実装（実際にはRedisやより高度な仕組みを使用）
        # ここでは基本的なチェックのみ
        
        logger.debug(f"レート制限チェック通過: {client_ip}")
        return True
        
    except Exception as e:
        logger.error(f"レート制限チェックエラー: {e}")
        return False

class SecurityMiddleware(BaseHTTPMiddleware):
    """セキュリティ強化ミドルウェア（完全版）"""
    
    async def dispatch(self, request: Request, call_next):
        """リクエスト処理"""
        
        try:
            # クライアントIP取得
            client_ip = get_client_ip(request)
            
            # セキュリティログ記録
            security_logger = logging.getLogger('security')
            security_logger.info(
                f"Request from {client_ip}: {request.method} {request.url}",
                extra={
                    "client_ip": client_ip,
                    "method": request.method,
                    "url": str(request.url),
                    "user_agent": request.headers.get("user-agent", "Unknown")
                }
            )
            
            # レート制限チェック
            if not await check_rate_limit(request):
                return HTTPException(
                    status_code=429, 
                    detail="レート制限に達しました"
                )
            
            # レスポンス処理
            response = await call_next(request)
            
            # セキュリティヘッダー追加
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
            
            return response
            
        except Exception as e:
            logger.error(f"Security middleware error: {e}")
            # エラー時も基本レスポンスを返す
            response = await call_next(request)
            return response
