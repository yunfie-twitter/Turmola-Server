"""
PostgreSQL データベース接続（ジョブ永続化）
"""

from sqlalchemy import create_engine, Column, String, DateTime, Text, Integer, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import logging
from typing import Optional, Dict, Any

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
    
def get_db() -> Session:
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
