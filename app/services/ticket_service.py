import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from ..services.cache_service import CacheService
from ..core.config import settings

logger = logging.getLogger(__name__)

class TicketService:
    """プレミアムチケット管理"""
    
    def __init__(self):
        self.cache = CacheService()
    
    async def validate_ticket(self, client_ip: str) -> bool:
        """チケット検証"""
        try:
            # IPアドレスに基づくチケット確認
            ticket_key = f"premium_ticket:{client_ip}"
            ticket_data = await self.cache.get(ticket_key)
            
            if not ticket_data:
                return False
            
            # 有効期限確認
            expires_at = datetime.fromisoformat(ticket_data['expires_at'])
            if expires_at < datetime.utcnow():
                await self.cache.delete(ticket_key)
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"チケット検証エラー: {e}")
            return False
    
    async def issue_ticket(self, client_ip: str, duration_days: int) -> bool:
        """チケット発行"""
        try:
            expires_at = datetime.utcnow() + timedelta(days=duration_days)
            
            ticket_data = {
                "issued_at": datetime.utcnow().isoformat(),
                "expires_at": expires_at.isoformat(),
                "duration_days": duration_days,
                "client_ip": client_ip
            }
            
            ticket_key = f"premium_ticket:{client_ip}"
            expire_seconds = duration_days * 24 * 3600
            
            return await self.cache.set(ticket_key, ticket_data, expire=expire_seconds)
            
        except Exception as e:
            logger.error(f"チケット発行エラー: {e}")
            return False
    
    async def revoke_ticket(self, client_ip: str) -> bool:
        """チケット無効化"""
        try:
            ticket_key = f"premium_ticket:{client_ip}"
            return await self.cache.delete(ticket_key)
        except Exception as e:
            logger.error(f"チケット無効化エラー: {e}")
            return False
    
    async def get_ticket_info(self, client_ip: str) -> Optional[Dict[str, Any]]:
        """チケット情報取得"""
        try:
            ticket_key = f"premium_ticket:{client_ip}"
            return await self.cache.get(ticket_key)
        except Exception as e:
            logger.error(f"チケット情報取得エラー: {e}")
            return None

# 便利関数
async def validate_ticket(client_ip: str) -> bool:
    """チケット検証（便利関数）"""
    service = TicketService()
    return await service.validate_ticket(client_ip)

async def get_server_type() -> str:
    """サーバー種別取得"""
    # 実装では管理者設定やライセンス情報に基づいて判定
    return "Premium"  # または "Normal"

async def get_job_limit(has_premium: bool) -> int:
    """ジョブ制限数取得"""
    if has_premium:
        return settings.MAX_CONCURRENT_JOBS_PREMIUM
    else:
        return settings.MAX_CONCURRENT_JOBS_NORMAL
