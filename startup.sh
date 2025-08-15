#!/bin/bash

# Turmola-Server v1.1 起動スクリプト（aria2統合版）

echo "🚀 Turmola-Server v1.1 起動中..."

# 環境変数確認
echo "Environment: ${ENVIRONMENT:-development}"
echo "Redis URL: ${REDIS_URL:-redis://localhost:6379/0}"
echo "aria2 Enabled: ${ENABLE_ARIA2:-false}"

# ディレクトリ作成
mkdir -p /app/downloads /app/logs /app/celerybeat

# aria2起動（有効な場合）
if [ "${ENABLE_ARIA2:-false}" = "true" ]; then
    echo "📡 aria2 daemon 起動中..."
    aria2c --enable-rpc \
           --rpc-listen-all=true \
           --rpc-listen-port=6800 \
           --rpc-secret="${ARIA2_SECRET:-turmola_secret}" \
           --dir="/app/downloads" \
           --max-concurrent-downloads=5 \
           --max-connection-per-server="${ARIA2_MAX_CONNECTIONS:-10}" \
           --split="${ARIA2_SPLITS:-10}" \
           --min-split-size=1M \
           --file-allocation=prealloc \
           --continue=true \
           --auto-file-renaming=false \
           --daemon=true \
           --log="/app/logs/aria2.log" \
           --log-level=info &
    
    # aria2起動確認
    sleep 3
    if curl -s "http://localhost:6800/jsonrpc" > /dev/null 2>&1; then
        echo "✅ aria2 daemon 起動完了"
    else
        echo "⚠️ aria2 daemon 起動に失敗、標準ダウンロードのみ使用"
    fi
fi

# 引数に応じてサービス起動
case "${1:-api}" in
    "api")
        echo "📡 FastAPI サーバー起動..."
        
        # 監視サービス開始（バックグラウンド）
        if [ "${ENABLE_PERFORMANCE_MONITORING:-false}" = "true" ]; then
            echo "📊 Performance monitoring 開始..."
            python -c "
import asyncio
from app.services.advanced_monitoring import advanced_monitoring
asyncio.run(advanced_monitoring.continuous_monitoring())
" &
        fi
        
        exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
        ;;
    "worker")
        echo "🔨 Celery ワーカー起動..."
        exec celery -A app.core.celery_app worker --loglevel=info --concurrency=4 --max-tasks-per-child=1000
        ;;
    "beat")
        echo "⏰ Celery Beat起動..."
        exec celery -A app.core.celery_app beat --loglevel=info --scheduler=celery.beat:PersistentScheduler
        ;;
    "flower")
        echo "🌸 Flower 起動..."
        exec celery -A app.core.celery_app flower --port=5555 --broker=redis://redis:6379/0
        ;;
    *)
        echo "❌ 無効なサービス名: $1"
        echo "使用可能: api, worker, beat, flower"
        exit 1
        ;;
esac
