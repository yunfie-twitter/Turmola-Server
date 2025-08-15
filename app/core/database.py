"""
PostgreSQL データベース接続（ジョブ永続化）- 修正版
"""

from sqlalchemy import create_engine, Column, String, DateTime, Text, Integer, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import logging
from typing import Optional, Dict, Any, Generator

from .config import settings

logger = logging.getLogger(__name__)

# データベースURL（環境変数で設定）
DATABASE_URL = settings.DATABASE_URL if hasattr(settings, 'DATABASE_URL') else "sqlite:///./turmola.db"

engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class JobRecord(Base):
    """ジョブ記録テーブル"""
    __tablename__ = "job_records"

    job_id = Column(String(36), primary_key=True, index=True)
    task_id = Column(String(36), index=True)
    url = Column(Text, nullable=False)
    status = Column(String(20), index=True, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    result_data = Column(JSON)
    options = Column(JSON)
    retry_count = Column(Integer, default=0)
    priority = Column(Integer, default=5)
    user_ip = Column(String(45))
    user_agent = Column(Text)

class SystemMetrics(Base):
    """システムメトリクス記録"""
    __tablename__ = "system_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    cpu_percent = Column(Integer)
    memory_percent = Column(Integer)
    disk_percent = Column(Integer)
    active_jobs = Column(Integer)
    pending_jobs = Column(Integer)
    failed_jobs_last_hour = Column(Integer)

# 修正: 正しい型注釈
def get_db() -> Generator[Session, None, None]:
    """データベースセッション取得"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_database():
    """データベース初期化"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("データベーステーブル作成完了")
    except Exception as e:
        logger.error(f"データベース初期化エラー: {e}")

# 追加: データベース接続確認関数
def check_database_connection() -> bool:
    """データベース接続確認"""
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        logger.info("データベース接続確認成功")
        return True
    except Exception as e:
        logger.error(f"データベース接続確認失敗: {e}")
        return False

# 追加: ジョブレコード操作関数
def create_job_record(
    job_id: str,
    url: str,
    options: Dict[str, Any] = None,
    user_ip: str = None,
    user_agent: str = None
) -> JobRecord:
    """ジョブレコード作成"""
    db = SessionLocal()
    try:
        job_record = JobRecord(
            job_id=job_id,
            url=url,
            options=options or {},
            user_ip=user_ip,
            user_agent=user_agent
        )
        db.add(job_record)
        db.commit()
        db.refresh(job_record)
        logger.info(f"ジョブレコード作成: {job_id}")
        return job_record
    except Exception as e:
        db.rollback()
        logger.error(f"ジョブレコード作成エラー: {e}")
        raise
    finally:
        db.close()

def update_job_status(
    job_id: str,
    status: str,
    task_id: str = None,
    error_message: str = None,
    result_data: Dict[str, Any] = None
) -> bool:
    """ジョブステータス更新"""
    db = SessionLocal()
    try:
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
            logger.info(f"ジョブステータス更新: {job_id} -> {status}")
            return True
        else:
            logger.warning(f"ジョブレコードが見つかりません: {job_id}")
            return False
            
    except Exception as e:
        db.rollback()
        logger.error(f"ジョブステータス更新エラー: {e}")
        return False
    finally:
        db.close()

def get_job_record(job_id: str) -> Optional[JobRecord]:
    """ジョブレコード取得"""
    db = SessionLocal()
    try:
        job_record = db.query(JobRecord).filter(JobRecord.job_id == job_id).first()
        return job_record
    except Exception as e:
        logger.error(f"ジョブレコード取得エラー: {e}")
        return None
    finally:
        db.close()

# 追加: システムメトリクス操作関数
def record_system_metrics(
    cpu_percent: int,
    memory_percent: int,
    disk_percent: int,
    active_jobs: int,
    pending_jobs: int,
    failed_jobs_last_hour: int
) -> SystemMetrics:
    """システムメトリクス記録"""
    db = SessionLocal()
    try:
        metrics = SystemMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            disk_percent=disk_percent,
            active_jobs=active_jobs,
            pending_jobs=pending_jobs,
            failed_jobs_last_hour=failed_jobs_last_hour
        )
        db.add(metrics)
        db.commit()
        db.refresh(metrics)
        logger.debug("システムメトリクス記録完了")
        return metrics
    except Exception as e:
        db.rollback()
        logger.error(f"システムメトリクス記録エラー: {e}")
        raise
    finally:
        db.close()

# 追加: データクリーンアップ関数
def cleanup_old_records(days: int = 30) -> int:
    """古いレコードのクリーンアップ"""
    from datetime import timedelta
    
    db = SessionLocal()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # 古いジョブレコードを削除
        deleted_jobs = db.query(JobRecord).filter(
            JobRecord.created_at < cutoff_date
        ).delete()
        
        # 古いシステムメトリクスを削除
        deleted_metrics = db.query(SystemMetrics).filter(
            SystemMetrics.timestamp < cutoff_date
        ).delete()
        
        db.commit()
        total_deleted = deleted_jobs + deleted_metrics
        logger.info(f"古いレコード削除: jobs={deleted_jobs}, metrics={deleted_metrics}")
        
        return total_deleted
        
    except Exception as e:
        db.rollback()
        logger.error(f"レコードクリーンアップエラー: {e}")
        return 0
    finally:
        db.close()
