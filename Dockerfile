FROM python:3.11-slim

# システムパッケージ更新
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリ設定
WORKDIR /app

# Python依存関係インストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコピー
COPY . .

# ディレクトリ作成
RUN mkdir -p /app/downloads /app/logs /app/celerybeat

# 権限設定
RUN chmod +x startup.sh || true

# ポート公開
EXPOSE 8000

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# デフォルトコマンド
CMD ["./startup.sh"]
