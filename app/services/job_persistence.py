"""
ジョブ永続化サービス
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from ..core.database import get_db, JobRecord, SystemMetrics
from ..core.config import settings

logger = logging.getLogger(__name__)

class JobPersistenceService:
    """ジョブ永続化管理"""
    
    @staticmethod
    def create_job_record(
        job_id: str,
        url: str,
        options: Dict[str, Any],
        user_ip: str = None,
        user_agent: str = None
    ) -> bool:
        """新規ジョブ記録作成"""
        try:
            db = next(get_db())
            job_record = JobRecord(
                job_id=job_id,
                url=url,
                options=options,
                user_ip=user_ip,
                user_agent=user_agent,
                created_at=datetime.utcnow()
            )
            db.add(job_record)
            db.commit()
            logger.info(f"ジョブ記録作成: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"ジョブ記録作成エラー: {e}")
            return False
    
    @staticmethod
    def update_job_status(
        job_id: str,
        status: str,
        task_id: str = None,
        error_message: str = None,
        result_data: Dict[str, Any] = None
    ) -> bool:
        """ジョブ状態更新"""
        try:
            db = next(get_db())
            job_record = db.query(JobRecord).filter(JobRecord.job_id == job_id).first()
            
            if job_record:
                job_record.status = status
                if task_id:
                    job_record.task_id = task_id
                if error_message:
                    job_record.error_message = error_message
                if result_data:
                    job_record.result_data = result_data
                
                if status == "running" and not job_record.started_at:
                    job_record.started_at = datetime.utcnow()
                elif status in ["success", "failed"]:
                    job_record.completed_at = datetime.utcnow()
                
                db.commit()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"ジョブ状態更新エラー: {e}")
            return False
    
    @staticmethod
    def get_failed_jobs_for_retry(max_retries: int = 3) -> List[JobRecord]:
        """リトライ対象の失敗ジョブ取得"""
        try:
            db = next(get_db())
            failed_jobs = db.query(JobRecord).filter(
                JobRecord.status == "failed",
                JobRecord.retry_count < max_retries,
                JobRecord.created_at > datetime.utcnow() - timedelta(hours=24)
            ).limit(10).all()
            
            return failed_jobs
            
        except Exception as e:
            logger.error(f"失敗ジョブ取得エラー: {e}")
            return []
    
    @staticmethod
    def cleanup_old_records(days: int = 30) -> int:
        """古いレコードのクリーンアップ"""
        try:
            db = next(get_db())
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            deleted_jobs = db.query(JobRecord).filter(
                JobRecord.created_at < cutoff_date
            ).delete()
            
            deleted_metrics = db.query(SystemMetrics).filter(
                SystemMetrics.timestamp < cutoff_date
            ).delete()
            
            db.commit()
            logger.info(f"古いレコード削除: jobs={deleted_jobs}, metrics={deleted_metrics}")
            
            return deleted_jobs + deleted_metrics
            
        except Exception as e:
            logger.error(f"レコードクリーンアップエラー: {e}")
            return 0
