"""
FastAPI メインアプリケーション（レート制限ON/OFF対応）
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from .core.config import settings
from .utils.rate_limiter import limiter
from .utils.logging import setup_logging
from .middleware.security import SecurityMiddleware
from .api import server_info, video_info, download, jobs, logs

# ロギング設定
setup_logging()

# FastAPIアプリケーション初期化
app = FastAPI(
    title="Turmola API",
    description="yt-dlpを使用した非同期動画ダウンロードAPI",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# レート制限設定（条件付き）
if settings.ENABLE_RATE_LIMITING:
    from slowapi.middleware import SlowAPIMiddleware
    
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    
    print(f"✅ レート制限有効: {settings.RATE_LIMIT_REQUESTS}回/{settings.RATE_LIMIT_WINDOW}秒")
    
    # レート制限エラーハンドラー
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={
                "error": "レート制限に達しました",
                "detail": "しばらく時間をおいてから再試行してください",
                "retry_after": str(exc.retry_after) if exc.retry_after else "60"
            }
        )
else:
    print("⚠️ レート制限無効")

# 既存のミドルウェアとルーター設定...
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ALLOWED_HOSTS == "*" else settings.ALLOWED_HOSTS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SecurityMiddleware)

# APIルーター登録
app.include_router(server_info.router, prefix="/api", tags=["Server"])
app.include_router(video_info.router, prefix="/api", tags=["Video Info"])
app.include_router(download.router, prefix="/api", tags=["Download"])
app.include_router(jobs.router, prefix="/api", tags=["Jobs"])
app.include_router(logs.router, prefix="/api", tags=["Logs"])

# レート制限エラーハンドラー[7]
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "error": "レート制限に達しました",
            "detail": "しばらく時間をおいてから再試行してください",
            "retry_after": str(exc.retry_after) if exc.retry_after else "60"
        }
    )

@app.on_event("startup")
async def startup_event():
    """アプリケーション起動時の処理"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Turmola が起動しました")
    
    # Redisへの接続確認
    from .core.redis_client import redis_client
    try:
        await redis_client.ping()
        logger.info("Redis接続成功")
    except Exception as e:
        logger.error(f"Redis接続失敗: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """アプリケーション終了時の処理"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Turmola Server が終了しました")

@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "message": "Turmola API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "healthy"}
