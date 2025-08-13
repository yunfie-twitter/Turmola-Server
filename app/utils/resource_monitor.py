"""
リソース監視システム
"""

import psutil
import os
import logging
from typing import Dict, Any
from datetime import datetime

from ..core.config import settings

logger = logging.getLogger(__name__)

class ResourceMonitor:
    """システムリソース監視クラス"""
    
    @staticmethod
    def get_system_stats() -> Dict[str, Any]:
        """システム統計情報取得"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # メモリ使用率
            memory = psutil.virtual_memory()
            
            # ディスク使用率
            disk = psutil.disk_usage(settings.STORAGE_PATH)
            
            # プロセス情報
            process = psutil.Process()
            process_memory = process.memory_info()
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "cpu": {
                    "percent": cpu_percent,
                    "count": psutil.cpu_count()
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": (disk.used / disk.total) * 100
                },
                "process": {
                    "memory_rss": process_memory.rss,
                    "memory_vms": process_memory.vms,
                    "cpu_percent": process.cpu_percent()
                }
            }
            
        except Exception as e:
            logger.error(f"システム統計取得エラー: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def check_resource_limits() -> Dict[str, Any]:
        """リソース制限チェック"""
        stats = ResourceMonitor.get_system_stats()
        warnings = []
        critical = []
        
        # メモリチェック
        if stats.get("memory", {}).get("percent", 0) > 90:
            critical.append("メモリ使用率が90%を超えています")
        elif stats.get("memory", {}).get("percent", 0) > 80:
            warnings.append("メモリ使用率が80%を超えています")
        
        # ディスクチェック
        if stats.get("disk", {}).get("percent", 0) > 95:
            critical.append("ディスク使用率が95%を超えています")
        elif stats.get("disk", {}).get("percent", 0) > 85:
            warnings.append("ディスク使用率が85%を超えています")
        
        # CPUチェック
        if stats.get("cpu", {}).get("percent", 0) > 95:
            critical.append("CPU使用率が95%を超えています")
        elif stats.get("cpu", {}).get("percent", 0) > 85:
            warnings.append("CPU使用率が85%を超えています")
        
        return {
            "status": "critical" if critical else ("warning" if warnings else "ok"),
            "warnings": warnings,
            "critical": critical,
            "stats": stats
        }
