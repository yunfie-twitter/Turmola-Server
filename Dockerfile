FROM python:3.11-slim

# 環境変数（UTF-8化）
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# システムパッケージ更新 & 必要ツールインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    aria2 \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリ設定
WORKDIR /app

# Python依存関係インストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーション一式コピー
COPY . .

# ログ/ダウンロード/beatディレクトリ作成 & 権限設定
RUN mkdir -p /app/downloads /app/logs /app/celerybeat \
    && groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app

# 実行権限付与
RUN chmod +x /app/startup.sh || true

# 非rootユーザーに切り替え
USER appuser

# ポート公開
EXPOSE 8000 6800

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# デフォルトコマンド
CMD ["./startup.sh"]
