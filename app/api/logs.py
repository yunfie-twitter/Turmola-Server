from fastapi import APIRouter, HTTPException, Query, Request
import logging
import os
from typing import Optional, List
from datetime import datetime, timedelta
from pathlib import Path

from ..models.server import LogEntry
from ..utils.rate_limiter import smart_rate_limit
from ..core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/logs", response_model=List[LogEntry])
@smart_rate_limit("10/minute")  # ログAPIは管理者用のため制限を厳しく
async def get_logs(
    request: Request,
    log_type: Optional[str] = Query(None, description="ログタイプ (app, security, jobs)"),
    level: Optional[str] = Query(None, description="ログレベル (DEBUG, INFO, WARNING, ERROR)"),
    limit: int = Query(100, ge=1, le=1000, description="取得件数"),
    start_date: Optional[str] = Query(None, description="開始日時 (YYYY-MM-DD HH:MM:SS)"),
    end_date: Optional[str] = Query(None, description="終了日時 (YYYY-MM-DD HH:MM:SS)")
):
    """ログを取得（管理者用）"""
    
    try:
        # 管理者認証チェック
        api_key = request.headers.get("X-Admin-Key")
        if api_key != getattr(settings, 'ADMIN_API_KEY', None):
            raise HTTPException(
                status_code=403,
                detail="管理者権限が必要です"
            )
        
        # ログファイルパス決定
        log_dir = Path(settings.LOG_FILE).parent
        log_files = []
        
        if log_type == "security":
            log_files.append(log_dir / "security.log")
        elif log_type == "jobs":
            log_files.append(log_dir / "jobs.log")
        elif log_type == "app" or log_type is None:
            log_files.append(log_dir / "app.log")
        else:
            log_files = [log_dir / "app.log", log_dir / "security.log", log_dir / "jobs.log"]
        
        logs = []
        
        for log_file in log_files:
            if not log_file.exists():
                continue
            
            try:
                # ログファイル読み込み（最新の行から取得）
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()[-limit:]  # 最新のlimit行を取得
                
                for line in reversed(lines):  # 新しい順に並べる
                    if line.strip():
                        log_entry = _parse_log_line(line.strip())
                        if log_entry:
                            # フィルタリング
                            if level and log_entry.level != level:
                                continue
                            
                            if start_date:
                                start_dt = datetime.fromisoformat(start_date)
                                if log_entry.timestamp < start_dt:
                                    continue
                            
                            if end_date:
                                end_dt = datetime.fromisoformat(end_date)
                                if log_entry.timestamp > end_dt:
                                    continue
                            
                            logs.append(log_entry)
                            
                            if len(logs) >= limit:
                                break
                
            except Exception as e:
                logger.error(f"ログファイル読み込みエラー: {log_file}, {e}")
        
        # ログを時刻順でソート
        logs.sort(key=lambda x: x.timestamp, reverse=True)
        
        return logs[:limit]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ログ取得エラー: {e}")
        raise HTTPException(
            status_code=500,
            detail="ログ取得中にエラーが発生しました"
        )

@router.get("/logs/summary")
@smart_rate_limit("20/minute")
async def get_log_summary(request: Request):
    """ログサマリーを取得"""
    
    try:
        # 管理者認証チェック
        api_key = request.headers.get("X-Admin-Key")
        if api_key != getattr(settings, 'ADMIN_API_KEY', None):
            raise HTTPException(
                status_code=403,
                detail="管理者権限が必要です"
            )
        
        log_dir = Path(settings.LOG_FILE).parent
        summary = {
            "log_files": {},
            "recent_errors": [],
            "stats": {
                "total_logs": 0,
                "error_count": 0,
                "warning_count": 0,
                "info_count": 0
            }
        }
        
        # ログファイル情報収集
        log_files = ["app.log", "security.log", "jobs.log"]
        
        for log_filename in log_files:
            log_file = log_dir / log_filename
            
            if log_file.exists():
                stat = log_file.stat()
                summary["log_files"][log_filename] = {
                    "size": stat.st_size,
                    "size_mb": stat.st_size / (1024 * 1024),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "exists": True
                }
                
                # 最新のエラーログを収集
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()[-100:]  # 最新100行
                        
                    for line in reversed(lines):
                        if "ERROR" in line:
                            summary["recent_errors"].append({
                                "file": log_filename,
                                "message": line.strip()
                            })
                            summary["stats"]["error_count"] += 1
                            
                            if len(summary["recent_errors"]) >= 10:
                                break
                        elif "WARNING" in line:
                            summary["stats"]["warning_count"] += 1
                        elif "INFO" in line:
                            summary["stats"]["info_count"] += 1
                        
                        summary["stats"]["total_logs"] += 1
                        
                except Exception as e:
                    logger.warning(f"ログファイル解析エラー: {log_filename}, {e}")
            else:
                summary["log_files"][log_filename] = {
                    "exists": False
                }
        
        summary["generated_at"] = datetime.utcnow().isoformat()
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ログサマリー取得エラー: {e}")
        raise HTTPException(
            status_code=500,
            detail="ログサマリー取得中にエラーが発生しました"
        )

@router.delete("/logs/clean")
@smart_rate_limit("2/hour")  # ログクリーンアップは厳しく制限
async def clean_old_logs(
    request: Request,
    days: int = Query(7, ge=1, le=30, description="保持日数")
):
    """古いログを削除（管理者用）"""
    
    try:
        # 管理者認証チェック
        api_key = request.headers.get("X-Admin-Key")
        if api_key != getattr(settings, 'ADMIN_API_KEY', None):
            raise HTTPException(
                status_code=403,
                detail="管理者権限が必要です"
            )
        
        log_dir = Path(settings.LOG_FILE).parent
        cutoff_time = datetime.now() - timedelta(days=days)
        
        cleaned_files = []
        total_size_freed = 0
        
        # ログファイルのローテーションファイルを削除
        for log_file in log_dir.glob("*.log.*"):
            if log_file.stat().st_mtime < cutoff_time.timestamp():
                size = log_file.stat().st_size
                log_file.unlink()
                cleaned_files.append(log_file.name)
                total_size_freed += size
        
        logger.info(f"ログクリーンアップ完了: {len(cleaned_files)}ファイル削除")
        
        return {
            "cleaned_files": cleaned_files,
            "total_files": len(cleaned_files),
            "size_freed_mb": total_size_freed / (1024 * 1024),
            "cutoff_days": days,
            "cleaned_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ログクリーンアップエラー: {e}")
        raise HTTPException(
            status_code=500,
            detail="ログクリーンアップ中にエラーが発生しました"
        )

def _parse_log_line(line: str) -> Optional[LogEntry]:
    """ログ行を解析してLogEntryオブジェクトを作成"""
    
    try:
        # 基本的なログ形式: "2025-01-01 12:00:00 - logger - LEVEL - message"
        parts = line.split(" - ", 3)
        
        if len(parts) < 4:
            return None
        
        timestamp_str = parts[0]
        logger_name = parts[1]
        level = parts[2]
        message = parts[3]
        
        # タイムスタンプ解析
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
        except:
            # フォーマットが違う場合の処理
            timestamp = datetime.now()
        
        return LogEntry(
            timestamp=timestamp,
            level=level,
            message=message,
            job_id=None,  # ログからの抽出は複雑なため省略
            ip_address=None,
            user_agent=None,
            extra={"logger": logger_name}
        )
        
    except Exception as e:
        logger.debug(f"ログ行解析エラー: {e}")
        return None
