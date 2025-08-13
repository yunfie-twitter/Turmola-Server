"""
メトリクス収集システム
"""

import psutil
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from dataclasses import dataclass
import json

from ..core.config import settings
from ..core.database import get_db, SystemMetrics

logger = logging.getLogger(__name__)

@dataclass
class MetricSnapshot:
    """メトリクススナップショット"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_io: Dict[str, int]
    active_jobs: int
    pending_jobs: int
    failed_jobs_last_hour: int
    response_time_avg: float

class MetricsCollector:
    """システムメトリクス収集"""
    
    def __init__(self):
        self.metrics_history: List[MetricSnapshot] = []
        self.max_history_size = 1000  # メモリ内保持数
    
    def collect_system_metrics(self) -> MetricSnapshot:
        """システムメトリクス収集"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # メモリ使用率
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # ディスク使用率
            disk = psutil.disk_usage(settings.STORAGE_PATH)
            disk_percent = (disk.used / disk.total) * 100
            
            # ネットワークI/O
            network = psutil.net_io_counters()
            network_io = {
                "bytes_sent": network.bytes_sent,
                "bytes_recv": network.bytes_recv,
                "packets_sent": network.packets_sent,
                "packets_recv": network.packets_recv
            }
            
            # ジョブ統計（Redisから取得）
            import redis
            redis_client = redis.from_url(settings.REDIS_URL)
            
            try:
                # アクティブジョブ数（簡易計算）
                active_jobs = len(redis_client.keys("job:*"))
                pending_jobs = redis_client.llen("celery")
                
                # 過去1時間の失敗ジョブ数
                failed_jobs_last_hour = self._count_failed_jobs_last_hour()
                
            except Exception as e:
                logger.warning(f"Job metrics collection error: {e}")
                active_jobs = pending_jobs = failed_jobs_last_hour = 0
            
            # レスポンス時間（APIエンドポイントの平均）
            response_time_avg = self._calculate_avg_response_time()
            
            snapshot = MetricSnapshot(
                timestamp=datetime.utcnow(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_percent=disk_percent,
                network_io=network_io,
                active_jobs=active_jobs,
                pending_jobs=pending_jobs,
                failed_jobs_last_hour=failed_jobs_last_hour,
                response_time_avg=response_time_avg
            )
            
            # メモリ内履歴に追加
            self.metrics_history.append(snapshot)
            if len(self.metrics_history) > self.max_history_size:
                self.metrics_history.pop(0)
            
            # データベースに保存
            self._save_to_database(snapshot)
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Metrics collection error: {e}")
            return None
    
    def _count_failed_jobs_last_hour(self) -> int:
        """過去1時間の失敗ジョブ数をカウント"""
        try:
            db = next(get_db())
            from ..core.database import JobRecord
            
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            count = db.query(JobRecord).filter(
                JobRecord.status == "failed",
                JobRecord.completed_at >= cutoff_time
            ).count()
            
            return count
            
        except Exception as e:
            logger.warning(f"Failed job count error: {e}")
            return 0
    
    def _calculate_avg_response_time(self) -> float:
        """平均レスポンス時間計算（簡易実装）"""
        # 実際の実装では、APIレスポンス時間をトラッキングして計算
        # ここでは概念的な値を返す
        return 50.0  # ms
    
    def _save_to_database(self, snapshot: MetricSnapshot):
        """メトリクスをデータベースに保存"""
        try:
            db = next(get_db())
            metric_record = SystemMetrics(
                timestamp=snapshot.timestamp,
                cpu_percent=int(snapshot.cpu_percent),
                memory_percent=int(snapshot.memory_percent),
                disk_percent=int(snapshot.disk_percent),
                active_jobs=snapshot.active_jobs,
                pending_jobs=snapshot.pending_jobs,
                failed_jobs_last_hour=snapshot.failed_jobs_last_hour
            )
            
            db.add(metric_record)
            db.commit()
            
        except Exception as e:
            logger.error(f"Metrics save error: {e}")
    
    def get_metrics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """メトリクス集計サマリー取得"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            recent_metrics = [
                m for m in self.metrics_history 
                if m.timestamp >= cutoff_time
            ]
            
            if not recent_metrics:
                return {}
            
            # 統計計算
            cpu_values = [m.cpu_percent for m in recent_metrics]
            memory_values = [m.memory_percent for m in recent_metrics]
            disk_values = [m.disk_percent for m in recent_metrics]
            
            return {
                "period_hours": hours,
                "sample_count": len(recent_metrics),
                "cpu": {
                    "avg": sum(cpu_values) / len(cpu_values),
                    "max": max(cpu_values),
                    "min": min(cpu_values)
                },
                "memory": {
                    "avg": sum(memory_values) / len(memory_values),
                    "max": max(memory_values),
                    "min": min(memory_values)
                },
                "disk": {
                    "avg": sum(disk_values) / len(disk_values),
                    "max": max(disk_values),
                    "min": min(disk_values)
                },
                "jobs": {
                    "total_failed_last_hour": recent_metrics[-1].failed_jobs_last_hour if recent_metrics else 0,
                    "avg_active": sum(m.active_jobs for m in recent_metrics) / len(recent_metrics),
                    "avg_pending": sum(m.pending_jobs for m in recent_metrics) / len(recent_metrics)
                }
            }
            
        except Exception as e:
            logger.error(f"Metrics summary error: {e}")
            return {}
    
    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """異常検知"""
        anomalies = []
        
        if len(self.metrics_history) < 10:
            return anomalies
        
        recent_metrics = self.metrics_history[-10:]  # 直近10サンプル
        
        # CPU使用率異常
        avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
        if avg_cpu > 90:
            anomalies.append({
                "type": "high_cpu",
                "severity": "critical",
                "value": avg_cpu,
                "threshold": 90,
                "message": f"High CPU usage detected: {avg_cpu:.1f}%"
            })
        
        # メモリ使用率異常
        avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
        if avg_memory > 85:
            anomalies.append({
                "type": "high_memory",
                "severity": "critical" if avg_memory > 95 else "warning",
                "value": avg_memory,
                "threshold": 85,
                "message": f"High memory usage detected: {avg_memory:.1f}%"
            })
        
        # 失敗ジョブ増加
        latest_failed = recent_metrics[-1].failed_jobs_last_hour
        if latest_failed > 10:
            anomalies.append({
                "type": "high_job_failures",
                "severity": "warning",
                "value": latest_failed,
                "threshold": 10,
                "message": f"High job failure rate: {latest_failed} failures in last hour"
            })
        
        return anomalies

# グローバルメトリクスコレクター
metrics_collector = MetricsCollector()
