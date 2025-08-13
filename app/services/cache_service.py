import json
import logging
from typing import Optional, Any, Dict
from ..core.redis_client import redis_client

logger = logging.getLogger(__name__)

class CacheService:
    """Redisキャッシュサービス"""
    
    def __init__(self):
        self.redis = redis_client
    
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """キャッシュから値を取得"""
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"キャッシュ取得エラー: {e}")
            return None
    
    async def set(self, key: str, value: Dict[str, Any], expire: Optional[int] = None) -> bool:
        """キャッシュに値を設定"""
        try:
            json_value = json.dumps(value, ensure_ascii=False, default=str)
            return await self.redis.set(key, json_value, ex=expire)
        except Exception as e:
            logger.error(f"キャッシュ設定エラー: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """キャッシュから値を削除"""
        try:
            return await self.redis.delete(key)
        except Exception as e:
            logger.error(f"キャッシュ削除エラー: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """キーの存在確認"""
        try:
            return await self.redis.exists(key)
        except Exception as e:
            logger.error(f"キャッシュ存在確認エラー: {e}")
            return False
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """カウンターを増加"""
        try:
            client = await self.redis.get_client()
            return await client.incrby(key, amount)
        except Exception as e:
            logger.error(f"カウンター増加エラー: {e}")
            return None
    
    async def expire(self, key: str, seconds: int) -> bool:
        """キーに有効期限を設定"""
        try:
            client = await self.redis.get_client()
            return await client.expire(key, seconds)
        except Exception as e:
            logger.error(f"有効期限設定エラー: {e}")
            return False
