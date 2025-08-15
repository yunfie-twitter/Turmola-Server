"""
高度な監視・アラートシステム
"""

import logging
import asyncio
import smtplib
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests

from ..core.config import settings
from ..utils.resource_monitor import ResourceMonitor

logger = logging.getLogger(__name__)

class AdvancedMonitoring:
    """高度な監視システム"""
    
    def __init__(self):
        self.alert_thresholds = {
            'cpu_critical': 95,
            'cpu_warning': 85,
            'memory_critical': 95,
            'memory_warning': 85,
            'disk_critical': 95,
            'disk_warning': 85,
            'job_failure_rate': 0.1,  # 10%
            'response_time_critical': 5000,  # 5秒
            'response_time_warning': 2000   # 2秒
        }
        
        self.alert_history = []
        self.max_alert_history = 1000
        
    async def continuous_monitoring(self):
        """継続監視プロセス"""
        while True:
            try:
                await self._perform_health_assessment()
                await asyncio.sleep(60)  # 1分間隔
                
            except Exception as e:
                logger.error(f"Continuous monitoring error: {e}")
                await asyncio.sleep(30)
    
    async def _perform_health_assessment(self):
        """包括的ヘルス評価"""
        try:
            # システムリソース監視
            resource_alerts = await self._check_resource_alerts()
            
            # アプリケーション監視
            app_alerts = await self._check_application_alerts()
            
            # パフォーマンス監視
            performance_alerts = await self._check_performance_alerts()
            
            # 依存関係監視
            dependency_alerts = await self._check_dependency_alerts()
            
            # 全アラート統合
            all_alerts = resource_alerts + app_alerts + performance_alerts + dependency_alerts
            
            # アラート処理
            if all_alerts:
                await self._process_alerts(all_alerts)
            
            # ヘルス履歴記録
            await self._record_health_snapshot(all_alerts)
            
        except Exception as e:
            logger.error(f"Health assessment error: {e}")
    
    async def _check_resource_alerts(self) -> List[Dict[str, Any]]:
        """リソースアラートチェック"""
        alerts = []
        
        try:
            stats = ResourceMonitor.get_system_stats()
            
            # CPU アラート
            cpu_percent = stats.get('cpu', {}).get('percent', 0)
            if cpu_percent > self.alert_thresholds['cpu_critical']:
                alerts.append({
                    'type': 'resource',
                    'severity': 'critical',
                    'metric': 'cpu',
                    'value': cpu_percent,
                    'threshold': self.alert_thresholds['cpu_critical'],
                    'message': f'Critical CPU usage: {cpu_percent:.1f}%'
                })
            elif cpu_percent > self.alert_thresholds['cpu_warning']:
                alerts.append({
                    'type': 'resource',
                    'severity': 'warning',
                    'metric': 'cpu',
                    'value': cpu_percent,
                    'threshold': self.alert_thresholds['cpu_warning'],
                    'message': f'High CPU usage: {cpu_percent:.1f}%'
                })
            
            # Memory アラート
            memory_percent = stats.get('memory', {}).get('percent', 0)
            if memory_percent > self.alert_thresholds['memory_critical']:
                alerts.append({
                    'type': 'resource',
                    'severity': 'critical',
                    'metric': 'memory',
                    'value': memory_percent,
                    'threshold': self.alert_thresholds['memory_critical'],
                    'message': f'Critical memory usage: {memory_percent:.1f}%'
                })
            elif memory_percent > self.alert_thresholds['memory_warning']:
                alerts.append({
                    'type': 'resource',
                    'severity': 'warning',
                    'metric': 'memory',
                    'value': memory_percent,
                    'threshold': self.alert_thresholds['memory_warning'],
                    'message': f'High memory usage: {memory_percent:.1f}%'
                })
            
            # Disk アラート
            disk_percent = stats.get('disk', {}).get('percent', 0)
            if disk_percent > self.alert_thresholds['disk_critical']:
                alerts.append({
                    'type': 'resource',
                    'severity': 'critical',
                    'metric': 'disk',
                    'value': disk_percent,
                    'threshold': self.alert_thresholds['disk_critical'],
                    'message': f'Critical disk usage: {disk_percent:.1f}%'
                })
            elif disk_percent > self.alert_thresholds['disk_warning']:
                alerts.append({
                    'type': 'resource',
                    'severity': 'warning',
                    'metric': 'disk',
                    'value': disk_percent,
                    'threshold': self.alert_thresholds['disk_warning'],
                    'message': f'High disk usage: {disk_percent:.1f}%'
                })
            
        except Exception as e:
            logger.error(f"Resource alert check error: {e}")
            alerts.append({
                'type': 'system',
                'severity': 'error',
                'metric': 'monitoring',
                'message': f'Resource monitoring failed: {str(e)}'
            })
        
        return alerts
    
    async def _check_application_alerts(self) -> List[Dict[str, Any]]:
        """アプリケーションアラートチェック"""
        alerts = []
        
        try:
            # ジョブ失敗率チェック
            failure_rate = await self._calculate_job_failure_rate()
            if failure_rate > self.alert_thresholds['job_failure_rate']:
                alerts.append({
                    'type': 'application',
                    'severity': 'warning' if failure_rate < 0.2 else 'critical',
                    'metric': 'job_failure_rate',
                    'value': failure_rate,
                    'threshold': self.alert_thresholds['job_failure_rate'],
                    'message': f'High job failure rate: {failure_rate:.1%}'
                })
            
            # 応答時間チェック
            avg_response_time = await self._measure_api_response_time()
            if avg_response_time > self.alert_thresholds['response_time_critical']:
                alerts.append({
                    'type': 'application',
                    'severity': 'critical',
                    'metric': 'response_time',
                    'value': avg_response_time,
                    'threshold': self.alert_thresholds['response_time_critical'],
                    'message': f'Critical API response time: {avg_response_time}ms'
                })
            elif avg_response_time > self.alert_thresholds['response_time_warning']:
                alerts.append({
                    'type': 'application',
                    'severity': 'warning',
                    'metric': 'response_time',
                    'value': avg_response_time,
                    'threshold': self.alert_thresholds['response_time_warning'],
                    'message': f'Slow API response time: {avg_response_time}ms'
                })
            
        except Exception as e:
            logger.error(f"Application alert check error: {e}")
        
        return alerts
    
    async def _check_performance_alerts(self) -> List[Dict[str, Any]]:
        """パフォーマンスアラートチェック"""
        alerts = []
        
        try:
            # キュー長チェック
            import redis
            redis_client = redis.from_url(settings.REDIS_URL)
            queue_length = redis_client.llen("celery")
            
            if queue_length > 100:
                alerts.append({
                    'type': 'performance',
                    'severity': 'warning' if queue_length < 200 else 'critical',
                    'metric': 'queue_length',
                    'value': queue_length,
                    'threshold': 100,
                    'message': f'High job queue length: {queue_length}'
                })
            
            # ワーカー数チェック
            from ..core.celery_app import celery_app
            inspect = celery_app.control.inspect()
            stats = inspect.stats() or {}
            worker_count = len(stats)
            
            if worker_count == 0:
                alerts.append({
                    'type': 'performance',
                    'severity': 'critical',
                    'metric': 'worker_count',
                    'value': worker_count,
                    'threshold': 1,
                    'message': 'No Celery workers available'
                })
            elif worker_count < 2:
                alerts.append({
                    'type': 'performance',
                    'severity': 'warning',
                    'metric': 'worker_count',
                    'value': worker_count,
                    'threshold': 2,
                    'message': f'Low worker count: {worker_count}'
                })
            
        except Exception as e:
            logger.error(f"Performance alert check error: {e}")
        
        return alerts
    
    async def _check_dependency_alerts(self) -> List[Dict[str, Any]]:
        """依存関係アラートチェック"""
        alerts = []
        
        try:
            # Redis接続チェック
            import redis
            redis_client = redis.from_url(settings.REDIS_URL)
            
            try:
                redis_client.ping()
            except Exception as e:
                alerts.append({
                    'type': 'dependency',
                    'severity': 'critical',
                    'metric': 'redis',
                    'message': f'Redis connection failed: {str(e)}'
                })
            
            # aria2ステータスチェック（有効な場合）
            if getattr(settings, 'ENABLE_ARIA2', False):
                from ..services.aria2_service import aria2_service
                if not await aria2_service.check_aria2_status():
                    alerts.append({
                        'type': 'dependency',
                        'severity': 'warning',
                        'metric': 'aria2',
                        'message': 'aria2 daemon is not responding'
                    })
            
        except Exception as e:
            logger.error(f"Dependency alert check error: {e}")
        
        return alerts
    
    async def _calculate_job_failure_rate(self) -> float:
        """ジョブ失敗率計算"""
        try:
            # 過去1時間のジョブ統計（簡易実装）
            # 実際のDBから取得する場合はここを修正
            return 0.05  # 5% (サンプル値)
        except Exception as e:
            logger.error(f"Job failure rate calculation error: {e}")
            return 0.0
    
    async def _measure_api_response_time(self) -> float:
        """API応答時間測定"""
        try:
            start_time = datetime.utcnow()
            
            # ヘルスチェックエンドポイントで測定
            response = requests.get(
                f"http://localhost:{settings.API_PORT}/health",
                timeout=10
            )
            
            end_time = datetime.utcnow()
            response_time = (end_time - start_time).total_seconds() * 1000
            
            if response.status_code == 200:
                return response_time
            else:
                return 9999  # エラー時は高い値を返す
                
        except Exception as e:
            logger.error(f"Response time measurement error: {e}")
            return 9999
    
    async def _process_alerts(self, alerts: List[Dict[str, Any]]):
        """アラート処理"""
        try:
            # 重要度別にグループ化
            critical_alerts = [a for a in alerts if a.get('severity') == 'critical']
            warning_alerts = [a for a in alerts if a.get('severity') == 'warning']
            
            # アラート履歴に追加
            for alert in alerts:
                alert['timestamp'] = datetime.utcnow().isoformat()
                self.alert_history.append(alert)
            
            # 履歴サイズ管理
            if len(self.alert_history) > self.max_alert_history:
                self.alert_history = self.alert_history[-self.max_alert_history:]
            
            # クリティカルアラートの即座通知
            if critical_alerts:
                await self._send_critical_alerts(critical_alerts)
            
            # 警告アラートの通知（頻度制限あり）
            if warning_alerts:
                await self._send_warning_alerts(warning_alerts)
            
        except Exception as e:
            logger.error(f"Alert processing error: {e}")
    
    async def _send_critical_alerts(self, alerts: List[Dict[str, Any]]):
        """クリティカルアラート送信"""
        try:
            # Slack通知
            if hasattr(settings, 'SLACK_WEBHOOK_URL'):
                await self._send_slack_alert(alerts, 'critical')
            
            # メール通知
            if hasattr(settings, 'ALERT_EMAIL'):
                await self._send_email_alert(alerts, 'critical')
            
            logger.warning(f"Critical alerts sent: {len(alerts)} alerts")
            
        except Exception as e:
            logger.error(f"Critical alert sending error: {e}")
    
    async def _send_warning_alerts(self, alerts: List[Dict[str, Any]]):
        """警告アラート送信（頻度制限）"""
        try:
            # 最後の警告から一定時間経過している場合のみ送信
            last_warning_time = getattr(self, '_last_warning_time', None)
            now = datetime.utcnow()
            
            if (not last_warning_time or 
                (now - last_warning_time).total_seconds() > 300):  # 5分間隔
                
                if hasattr(settings, 'SLACK_WEBHOOK_URL'):
                    await self._send_slack_alert(alerts, 'warning')
                
                self._last_warning_time = now
                logger.info(f"Warning alerts sent: {len(alerts)} alerts")
            
        except Exception as e:
            logger.error(f"Warning alert sending error: {e}")
    
    async def _send_slack_alert(self, alerts: List[Dict[str, Any]], severity: str):
        """Slack アラート送信"""
        try:
            webhook_url = getattr(settings, 'SLACK_WEBHOOK_URL', None)
            if not webhook_url:
                return
            
            color = "#ff0000" if severity == 'critical' else "#ffaa00"
            icon = "🚨" if severity == 'critical' else "⚠️"
            
            message = {
                "username": "Turmola-Server Monitor",
                "icon_emoji": ":warning:",
                "attachments": [{
                    "color": color,
                    "title": f"{icon} {severity.upper()} Alert - Turmola-Server",
                    "fields": []
                }]
            }
            
            for alert in alerts[:5]:  # 最大5件まで
                message["attachments"][0]["fields"].append({
                    "title": alert.get('metric', 'Unknown'),
                    "value": alert.get('message', 'No message'),
                    "short": True
                })
            
            if len(alerts) > 5:
                message["attachments"][0]["fields"].append({
                    "title": "Additional Alerts",
                    "value": f"... and {len(alerts) - 5} more alerts",
                    "short": True
                })
            
            response = requests.post(webhook_url, json=message, timeout=10)
            response.raise_for_status()
            
        except Exception as e:
            logger.error(f"Slack alert sending error: {e}")
    
    async def _send_email_alert(self, alerts: List[Dict[str, Any]], severity: str):
        """メールアラート送信"""
        try:
            alert_email = getattr(settings, 'ALERT_EMAIL', None)
            smtp_server = getattr(settings, 'SMTP_SERVER', 'localhost')
            smtp_port = getattr(settings, 'SMTP_PORT', 587)
            smtp_user = getattr(settings, 'SMTP_USER', None)
            smtp_password = getattr(settings, 'SMTP_PASSWORD', None)
            
            if not alert_email:
                return
            
            # メール内容作成
            subject = f"[{severity.upper()}] Turmola-Server Alert"
            
            body = f"Turmola-Server Alert Report\n"
            body += f"Severity: {severity.upper()}\n"
            body += f"Timestamp: {datetime.utcnow().isoformat()}\n\n"
            body += "Alerts:\n"
            
            for i, alert in enumerate(alerts, 1):
                body += f"{i}. {alert.get('message', 'No message')}\n"
                if alert.get('value') and alert.get('threshold'):
                    body += f"   Value: {alert['value']} (Threshold: {alert['threshold']})\n"
                body += "\n"
            
            # メール送信
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = smtp_user or 'turmola@localhost'
            msg['To'] = alert_email
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if smtp_user and smtp_password:
                    server.starttls()
                    server.login(smtp_user, smtp_password)
                server.send_message(msg)
            
        except Exception as e:
            logger.error(f"Email alert sending error: {e}")
    
    async def _record_health_snapshot(self, alerts: List[Dict[str, Any]]):
        """ヘルススナップショット記録"""
        try:
            snapshot = {
                'timestamp': datetime.utcnow().isoformat(),
                'alert_count': len(alerts),
                'critical_count': len([a for a in alerts if a.get('severity') == 'critical']),
                'warning_count': len([a for a in alerts if a.get('severity') == 'warning']),
                'overall_status': 'critical' if any(a.get('severity') == 'critical' for a in alerts) else 
                                'warning' if alerts else 'healthy'
            }
            
            # Redis に記録（24時間保持）
            import redis
            redis_client = redis.from_url(settings.REDIS_URL)
            redis_client.setex(
                f"health_snapshot:{int(datetime.utcnow().timestamp())}",
                86400,  # 24時間
                json.dumps(snapshot)
            )
            
        except Exception as e:
            logger.error(f"Health snapshot recording error: {e}")
    
    def get_recent_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """最近のアラート取得"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            recent_alerts = []
            for alert in self.alert_history:
                try:
                    alert_time = datetime.fromisoformat(alert['timestamp'])
                    if alert_time >= cutoff_time:
                        recent_alerts.append(alert)
                except:
                    continue
            
            return recent_alerts
            
        except Exception as e:
            logger.error(f"Recent alerts retrieval error: {e}")
            return []

# グローバル監視サービス
advanced_monitoring = AdvancedMonitoring()
