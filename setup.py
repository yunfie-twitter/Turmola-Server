#!/usr/bin/env python3
"""
Video Downloader API - マルチOS対応セットアップスクリプト
Python 3.6+ 対応
"""

import os
import sys
import platform
import subprocess
import secrets
import string
import shutil
from pathlib import Path
import argparse

class Colors:
    """ANSIカラーコード（Windows対応）"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    CYAN = '\033[0;36m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'
    
    @classmethod
    def disable_on_windows(cls):
        if platform.system() == "Windows":
            cls.RED = cls.GREEN = cls.YELLOW = cls.CYAN = cls.BLUE = cls.NC = ""

def print_colored(text, color=Colors.NC):
    print(f"{color}{text}{Colors.NC}")

def run_command(command, shell=True, check=True):
    try:
        result = subprocess.run(command, shell=shell, check=check, 
                                capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr
    except FileNotFoundError:
        return False, "", "Command not found"

def check_docker():
    print_colored("Docker環境をチェックしています...", Colors.BLUE)
    
    success, _, _ = run_command("docker --version", check=False)
    if not success:
        print_colored("Docker がインストールされていません", Colors.RED)
        print_colored("https://www.docker.com/products/docker-desktop からインストールしてください", Colors.YELLOW)
        return False
    
    success, _, _ = run_command("docker-compose --version", check=False)
    if not success:
        success, _, _ = run_command("docker compose version", check=False)
        if not success:
            print_colored("docker-compose がインストールされていません", Colors.RED)
            return False
    
    print_colored("Docker環境が利用可能です", Colors.GREEN)
    return True

def generate_secret_key(length=64):
    characters = string.ascii_letters + string.digits + "!@#$%^&*()_+-="
    return ''.join(secrets.choice(characters) for _ in range(length))

def create_env_file(secret_key, premium_api_key):
    env_content = f"""# Redis Configuration
REDIS_URL=redis://redis:6379/0
REDIS_RESULT_BACKEND=redis://redis:6379/1
REDIS_PASSWORD=

# Celery Configuration
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
SECRET_KEY={secret_key}

# Download Configuration
STORAGE_PATH=/app/downloads
MAX_CONCURRENT_JOBS_PREMIUM=10
MAX_CONCURRENT_JOBS_NORMAL=3
CACHE_TTL=3600

# Rate Limiting
RATE_LIMIT_REQUESTS=10
RATE_LIMIT_WINDOW=60

# Logging
LOG_LEVEL=INFO
LOG_FILE=/app/logs/app.log

# Premium Ticket Configuration
PREMIUM_API_KEY={premium_api_key}

# Security
ALLOWED_HOSTS=*

# File Cleanup
CLEANUP_INTERVAL_HOURS=24
MAX_FILE_AGE_DAYS=7
MAX_STORAGE_GB=100

# Environment
ENVIRONMENT=development
"""
    with open('.env', 'w', encoding='utf-8') as f:
        f.write(env_content)
    print_colored(".env ファイルを生成しました", Colors.GREEN)

def create_requirements_file():
    """requirements.txt を固定内容で作成"""
    requirements_content = """fastapi==0.104.1
uvicorn[standard]==0.24.0
celery[redis]==5.4.0
redis==5.0.1
flower==2.0.1
yt-dlp
pydantic==2.5.2
pydantic-settings==2.1.0
slowapi==0.1.9
python-multipart==0.0.6
aiofiles==23.2.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
psutil==5.9.6
requests==2.31.0
supervisor==4.2.5
"""
    with open('requirements.txt', 'w', encoding='utf-8') as f:
        f.write(requirements_content)
    print_colored("requirements.txt を生成しました", Colors.GREEN)

def create_startup_script():
    startup_content = """#!/bin/bash

if [ -z "$REDIS_URL" ]; then
    echo "Error: REDIS_URL is not set"
    exit 1
fi

mkdir -p /app/downloads /app/logs

echo "Waiting for Redis..."
while ! redis-cli -u $REDIS_URL ping > /dev/null 2>&1; do
    echo "Waiting for Redis to be ready..."
    sleep 2
done
echo "Redis is ready!"

echo "Starting Video Downloader API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
"""
    with open('startup.sh', 'w', encoding='utf-8', newline='\n') as f:
        f.write(startup_content)
    
    if platform.system() != "Windows":
        os.chmod('startup.sh', 0o755)
    print_colored("startup.sh を生成しました", Colors.GREEN)

def create_directories():
    directories = ['downloads', 'logs', 'celerybeat']
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
    print_colored("必要なディレクトリを作成しました", Colors.GREEN)

def set_permissions(os_type):
    if os_type == "Windows":
        print_colored("Windows環境: 権限設定をスキップしました", Colors.YELLOW)
        return True
    
    directories = ['downloads', 'logs', 'celerybeat']
    for directory in directories:
        try:
            success, _, _ = run_command(f"chown -R 1000:1000 {directory}", check=False)
            if not success:
                success, _, _ = run_command(f"sudo chown -R 1000:1000 {directory}", check=False)
        except Exception:
            print_colored(f"{directory} の権限設定をスキップしました", Colors.YELLOW)
    
    print_colored("ディレクトリ権限を設定しました", Colors.GREEN)
    return True

def clone_repository(repo_url, target_folder, force=False):
    if Path(target_folder).exists():
        if force:
            print_colored(f"{target_folder} を削除して再クローンします...", Colors.YELLOW)
            shutil.rmtree(target_folder)
        else:
            print_colored(f"{target_folder} は既に存在します。--force で上書きできます。", Colors.RED)
            return False
    print_colored(f"GitHubリポジトリをクローンしています: {repo_url}", Colors.BLUE)
    success, out, err = run_command(f"git clone {repo_url} {target_folder}")
    if not success:
        print_colored(f"Gitクローン失敗: {err}", Colors.RED)
        return False
    print_colored("クローン完了", Colors.GREEN)
    return True

def main():
    parser = argparse.ArgumentParser(description='Video Downloader API セットアップスクリプト')
    parser.add_argument('--force', action='store_true', help='既存ディレクトリを上書き')
    parser.add_argument('--secret-key', help='カスタムSECRET_KEY')
    parser.add_argument('--premium-api-key', help='カスタムPREMIUM_API_KEY')
    parser.add_argument('--skip-docker', action='store_true', help='Docker起動をスキップ')
    
    args = parser.parse_args()
    
    os_type = platform.system()
    if os_type == "Windows":
        Colors.disable_on_windows()
    
    print_colored(f"=== Video Downloader API セットアップ ({os_type}) ===", Colors.GREEN)
    
    project_folder = "build"
    Path(project_folder).mkdir(exist_ok=True)
    os.chdir(project_folder)
    print_colored(f"プロジェクトフォルダ作成/移動: {project_folder}", Colors.GREEN)
    
    # GitHubクローン
    repo_url = "https://github.com/yunfie-twitter/Turmola-Server.git"
    target_folder = "Turmola-Server"
    if not clone_repository(repo_url, target_folder, force=args.force):
        return 1
    
    # Turmola-Server 内でファイル生成
    os.chdir(target_folder)
    print_colored(f"{target_folder} 内でファイル生成を開始します...", Colors.BLUE)
    
    if not args.skip_docker and not check_docker():
        return 1
    
    create_directories()
    set_permissions(os_type)
    
    secret_key = args.secret_key or generate_secret_key(64)
    premium_api_key = args.premium_api_key or generate_secret_key(32)
    
    if not args.secret_key:
        print_colored("SECRET_KEYを自動生成しました", Colors.GREEN)
    if not args.premium_api_key:
        print_colored("PREMIUM_API_KEYを自動生成しました", Colors.GREEN)
    
    create_env_file(secret_key, premium_api_key)
    create_requirements_file()
    create_startup_script()
    
    print_colored("=== セットアップ完了 ===", Colors.GREEN)
    print_colored(f"API URL: http://localhost:8000", Colors.CYAN)
    print_colored(f"SECRET_KEY: {secret_key}", Colors.YELLOW)
    print_colored(f"PREMIUM_API_KEY: {premium_api_key}", Colors.YELLOW)
    print_colored(f"プロジェクトディレクトリ: {Path.cwd()}", Colors.CYAN)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
