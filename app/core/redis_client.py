import redis.asyncio as redis
import logging
from typing import Optional

from .config import settings

logger = logging.getLogger(__name__)

class RedisClient:
    """Redis非同期クライアント"""
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._connection_retries = 3
        
    async def get_client(self) -> redis.Redis:
        """Redis接続を取得"""
        if self._client is None:
            await self._connect()
        return self._client
    
    async def _connect(self):
        """Redis接続確立"""
        for attempt in range(self._connection_retries):
            try:
                self._client = redis.from_url(
                    settings.REDIS_URL,
                    password=settings.REDIS_PASSWORD,
                    encoding="utf-8",
                    decode_responses=True,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                
                # 接続テスト
                await self._client.ping()
                logger.info("Redis接続が確立されました")
                return
                
            except Exception as e:
                logger.error(f"Redis接続試行 {attempt + 1}/{self._connection_retries} 失敗: {e}")
                if attempt == self._connection_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
    
    async def ping(self) -> bool:
        """Redis接続確認"""
        try:
            client = await self.get_client()
            return await client.ping()
        except Exception as e:
            logger.error(f"Redis ping失敗: {e}")
            return False
    
    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """値設定"""
        try:
            client = await self.get_client()
            return await client.set(key, value, ex=ex)
        except Exception as e:
            logger.error(f"Redis set失敗: {e}")
            return False
    
    async def get(self, key: str) -> Optional[str]:
        """値取得"""
        try:
            client = await self.get_client()
            return await client.get(key)
        except Exception as e:
            logger.error(f"Redis get失敗: {e}")
            return None
    
    async def delete(self, key: str) -> bool:
        """値削除"""
        try:
            client = await self.get_client()
            return bool(await client.delete(key))
        except Exception as e:
            logger.error(f"Redis delete失敗: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """キー存在確認"""
        try:
            client = await self.get_client()
            return bool(await client.exists(key))
        except Exception as e:
            logger.error(f"Redis exists失敗: {e}")
            return False

# グローバルインスタンス
redis_client = RedisClient()
