from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request
from functools import wraps
import asyncio
from typing import Callable, Any

from ..core.config import settings

def get_client_id(request: Request) -> str:
    
    # プレミアムユーザーの識別
    api_key = request.headers.get("X-API-Key")
    if api_key == settings.PREMIUM_API_KEY:
        return f"premium:{get_remote_address(request)}"
    
    # 通常のIPベース識別
    return get_remote_address(request)

def get_rate_limiter() -> Limiter:
    """レート制限設定を取得"""
    
    return Limiter(
        key_func=get_client_id,
        default_limits=[f"{settings.RATE_LIMIT_REQUESTS}/minute"] if settings.ENABLE_RATE_LIMITING else []
    )

# グローバルリミッター
limiter = get_rate_limiter()

def flexible_rate_limit(normal_rate: str, premium_rate: str = None):
    def decorator(func: Callable) -> Callable:
        if not settings.ENABLE_RATE_LIMITING:
            return func
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # リクエストオブジェクトを探す
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if request:
                # プレミアムユーザーチェック
                api_key = request.headers.get("X-API-Key")
                if api_key == settings.PREMIUM_API_KEY and premium_rate:
                    # プレミアムユーザーには緩いレート制限
                    limited_func = limiter.limit(premium_rate)(func)
                else:
                    # 通常ユーザー
                    limited_func = limiter.limit(normal_rate)(func)
                
                return await limited_func(*args, **kwargs)
            else:
                # Requestが見つからない場合は通常制限
                limited_func = limiter.limit(normal_rate)(func)
                return await limited_func(*args, **kwargs)
        
        return async_wrapper
    return decorator

def smart_rate_limit(rate: str):
    def decorator(func: Callable) -> Callable:
        if not settings.ENABLE_RATE_LIMITING:
            return func
        
        # レート制限有効時の処理
        limited_func = limiter.limit(rate)(func)
        
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await limited_func(*args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return limited_func(*args, **kwargs)
            return sync_wrapper
    return decorator
