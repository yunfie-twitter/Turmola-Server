"""
分散ロックシステム（Redis ベース）
"""

import redis
import time
import logging
import uuid
from typing import Optional, Any
from contextlib import contextmanager

from ..core.config import settings

logger = logging.getLogger(__name__)

class DistributedLock:
    """Redis ベース分散ロック"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client or redis.from_url(settings.REDIS_URL)
        self.lock_id = str(uuid.uuid4())
    
    @contextmanager
    def acquire(
        self,
        key: str,
        timeout: int = 300,
        blocking_timeout: int = 10,
        auto_renewal: bool = True
    ):
        """
        分散ロック取得（コンテキストマネージャー）
        
        Args:
            key: ロックキー
            timeout: ロック保持時間（秒）
            blocking_timeout: ロック取得待機時間（秒）
            auto_renewal: 自動更新フラグ
        """
        lock_acquired = False
        renewal_task = None
        
        try:
            # ロック取得試行
            lock_acquired = self._acquire_lock(key, timeout, blocking_timeout)
            
            if not lock_acquired:
                raise TimeoutError(f"Failed to acquire lock: {key}")
            
            # 自動更新タスク開始
            if auto_renewal:
                renewal_task = self._start_renewal_task(key, timeout)
            
            logger.info(f"Distributed lock acquired: {key}")
            yield self
            
        finally:
            # 自動更新停止
            if renewal_task:
                renewal_task = None
            
            # ロック解放
            if lock_acquired:
                self._release_lock(key)
                logger.info(f"Distributed lock released: {key}")
    
    def _acquire_lock(self, key: str, timeout: int, blocking_timeout: int) -> bool:
        """ロック取得処理"""
        lock_key = f"lock:{key}"
        end_time = time.time() + blocking_timeout
        
        while time.time() < end_time:
            # SET NX EX でアトミックにロック取得
            result = self.redis_client.set(
                lock_key,
                self.lock_id,
                nx=True,  # キーが存在しない場合のみ設定
                ex=timeout  # 有効期限設定
            )
            
            if result:
                return True
            
            # 短時間待機してリトライ
            time.sleep(0.1)
        
        return False
    
    def _release_lock(self, key: str) -> bool:
        """ロック解放処理"""
        lock_key = f"lock:{key}"
        
        # Lua スクリプトでアトミックにロック解放
        lua_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """
        
        try:
            result = self.redis_client.eval(lua_script, 1, lock_key, self.lock_id)
            return result == 1
        except Exception as e:
            logger.error(f"Lock release error: {e}")
            return False
    
    def _start_renewal_task(self, key: str, timeout: int):
        """ロック自動更新タスク（簡易実装）"""
        # 実際の実装では別スレッドまたは非同期タスクで実行
        # ここでは概念的な実装のみ
        pass
    
    @classmethod
    def with_lock(cls, key: str, timeout: int = 300):
        """デコレータ形式でのロック使用"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                lock = cls()
                with lock.acquire(key, timeout):
                    return func(*args, **kwargs)
            return wrapper
        return decorator

# 使用例用のヘルパー関数
def synchronized(lock_key: str, timeout: int = 300):
    """同期処理デコレータ"""
    return DistributedLock.with_lock(lock_key, timeout)
