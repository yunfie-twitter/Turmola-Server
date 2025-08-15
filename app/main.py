"""
Turmola-Server v1.1 メインアプリケーション（統合完全版）
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

# ロガー定義
logger = logging.getLogger("app.main")

# 設定とユーティリティのインポート
from .core.config import settings
from .utils.rate_limiter import limiter
from .utils.logging_config import setup_logging

# ミドルウェアのインポート
from .middleware.security import SecurityMiddleware

# APIルーターのインポート
from .api import server_info, video_info, download, jobs, logs
from .api import health, monitoring

def setup_complete_logging():
    """完全版ロギング設定"""
    try:
        # ログディレクトリ作成
        import os
        os.makedirs('/app/logs', exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('/app/logs/app.log', encoding='utf-8')
            ]
        )
        
        # 外部ライブラリのログレベル調整
        logging.getLogger("uvicorn").setLevel(logging.WARNING)
        logging.getLogger("fastapi").setLevel(logging.WARNING)
        logging.getLogger("slowapi").setLevel(logging.WARNING)
        
        logger.info("ロギング設定完了")
        
    except Exception as e:
        print(f"ロギング設定エラー: {e}")
        # フォールバック設定
        logging.basicConfig(level=logging.INFO)

# アプリケーションライフサイクル管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーション起動・終了処理"""
    
    # 起動時処理
    try:
        setup_complete_logging()
        logger.info("Turmola-Server v1.1 が起動しました")
        
        # Redis接続確認
        try:
            from .core.redis_client import redis_client
            await redis_client.ping()
            logger.info("Redis接続成功")
        except Exception as e:
            logger.error(f"Redis接続失敗: {e}")
            raise
        
        # フェイルオーバーサービス開始（安全チェック）
        if getattr(settings, 'ENABLE_FAILOVER', False):
            try:
                from .services.failover_service import failover_service
                asyncio.create_task(failover_service.start_heartbeat())
                logger.info("フェイルオーバーサービス開始")
            except Exception as e:
                logger.warning(f"フェイルオーバーサービス開始失敗: {e}")
        
        # レート制限設定表示
        if getattr(settings, 'ENABLE_RATE_LIMITING', False):
            logger.info(f"✅ レート制限有効: {getattr(settings, 'RATE_LIMIT_REQUESTS', '100')}回/{getattr(settings, 'RATE_LIMIT_WINDOW', '60')}秒")
        else:
            logger.warning("⚠️ レート制限無効")
        
        yield
        
    except Exception as e:
        logger.error(f"起動時エラー: {e}")
        raise
    
    # 終了時処理
    finally:
        logger.info("Turmola-Server v1.1 が終了します")

# FastAPIアプリケーション作成
app = FastAPI(
    title="Turmola-Server",
    description="高機能動画ダウンロード API サーバー v1.1",
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if getattr(settings, 'ALLOWED_HOSTS', "*") == "*" else getattr(settings, 'ALLOWED_HOSTS', "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# セキュリティミドルウェア
app.add_middleware(SecurityMiddleware)

# レート制限ミドルウェア（条件付き）
if getattr(settings, 'ENABLE_RATE_LIMITING', False):
    try:
        from slowapi.middleware import SlowAPIMiddleware
        
        app.state.limiter = limiter
        app.add_middleware(SlowAPIMiddleware)
        
        print(f"✅ レート制限有効: {getattr(settings, 'RATE_LIMIT_REQUESTS', '100')}回/{getattr(settings, 'RATE_LIMIT_WINDOW', '60')}秒")
        
    except ImportError as e:
        logger.warning(f"SlowAPI インポートエラー: {e}")
        logger.warning("⚠️ レート制限無効（slowapi未インストール）")
else:
    print("⚠️ レート制限無効")

# APIルーター登録
app.include_router(server_info.router, prefix="/api", tags=["サーバー情報"])
app.include_router(video_info.router, prefix="/api", tags=["動画情報"])
app.include_router(download.router, prefix="/api", tags=["ダウンロード"])
app.include_router(jobs.router, prefix="/api", tags=["ジョブ管理"])
app.include_router(logs.router, prefix="/api", tags=["ログ"])
app.include_router(health.router, prefix="/api", tags=["ヘルスチェック"])
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["監視"])

# エラーハンドラー
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """レート制限エラーハンドラー"""
    logger.warning(f"レート制限に達しました - IP: {request.client.host}")
    return JSONResponse(
        status_code=429,
        content={
            "error": "レート制限に達しました",
            "detail": "しばらく時間をおいてから再試行してください",
            "retry_after": str(exc.retry_after) if exc.retry_after else "60"
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """グローバル例外ハンドラー"""
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "内部サーバーエラーが発生しました"}
    )

# ルートエンドポイント
@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "message": "Turmola-Server v1.1 が稼働中です",
        "version": "1.1.0",
        "status": "active",
        "docs": "/docs",
        "features": {
            "rate_limiting": getattr(settings, 'ENABLE_RATE_LIMITING', False),
            "failover": getattr(settings, 'ENABLE_FAILOVER', False),
            "aria2": getattr(settings, 'ENABLE_ARIA2', False),
            "monitoring": getattr(settings, 'ENABLE_PERFORMANCE_MONITORING', False)
        }
    }

# デバッグ情報エンドポイント
@app.get("/api/debug/status")
async def debug_status():
    """デバッグ用ステータス情報"""
    return {
        "timestamp": "2025-08-15T17:53:00+09:00",
        "environment": getattr(settings, 'ENVIRONMENT', 'unknown'),
        "redis_url": getattr(settings, 'REDIS_URL', 'not_configured'),
        "storage_path": getattr(settings, 'STORAGE_PATH', '/app/downloads'),
        "log_level": logging.getLogger().level,
        "middleware_stack": [
            "CORSMiddleware",
            "SecurityMiddleware",
            "SlowAPIMiddleware" if getattr(settings, 'ENABLE_RATE_LIMITING', False) else None
        ]
    }

# 開発サーバー起動（直接実行時）
if __name__ == "__main__":
    import uvicorn
    
    setup_complete_logging()
    logger.info("開発サーバーモードで起動")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
