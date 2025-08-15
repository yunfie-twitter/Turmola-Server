"""
ユーティリティ関数（完全版）
日本語ファイル名対応 + 必要な全関数
"""

import re
import unicodedata
import hashlib
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import urlparse, parse_qs
import requests

logger = logging.getLogger(__name__)

# =============================================================================
# ファイル名処理関数
# =============================================================================

def sanitize_filename(filename: str) -> str:
    """
    ファイル名をサニタイズ（日本語完全対応版）
    """
    if not filename:
        return "untitled"
    
    # 拡張子を分離
    path = Path(filename)
    stem = path.stem
    suffix = path.suffix
    
    # 危険な文字を除去（Windows/Linux/macOS共通）
    dangerous_chars = r'[<>:"/\\|?*]'
    stem = re.sub(dangerous_chars, '', stem)
    
    # 制御文字と不可視文字を除去
    stem = ''.join(char for char in stem if unicodedata.category(char)[0] != 'C')
    
    # 先頭・末尾の空白とドットを除去
    stem = stem.strip('. ')
    
    # 予約語チェック（Windows）
    reserved_names = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    
    if stem.upper() in reserved_names:
        stem = f"_{stem}"
    
    # 空の場合はデフォルト名
    if not stem:
        stem = "untitled"
    
    # ファイル名を再構築
    safe_filename = stem + suffix
    
    # 長さ制限（255バイト - UTF-8考慮）
    safe_filename = limit_filename_bytes(safe_filename, 255)
    
    return safe_filename

def limit_filename_bytes(filename: str, max_bytes: int = 255) -> str:
    """
    ファイル名のバイト長を制限（UTF-8）
    """
    encoded = filename.encode('utf-8')
    
    if len(encoded) <= max_bytes:
        return filename
    
    # 拡張子を保持しながら調整
    path = Path(filename)
    stem = path.stem
    suffix = path.suffix
    
    # 拡張子分のバイトを確保
    suffix_bytes = len(suffix.encode('utf-8'))
    available_bytes = max_bytes - suffix_bytes - 10  # 安全マージン
    
    # stemを切り詰める
    truncated = ''
    for char in stem:
        test_name = truncated + char
        if len(test_name.encode('utf-8')) <= available_bytes:
            truncated += char
        else:
            break
    
    return truncated + suffix

def sanitize_filename_with_info(filename: str, video_info: Dict[str, Any] = None) -> str:
    """
    動画情報を使った賢いファイル名生成（日本語対応）
    """
    # 基本のサニタイズ
    safe_name = sanitize_filename(filename)
    
    # 日本語が除去されすぎた場合の対策
    if (len(safe_name) < 5 or 
        safe_name.replace('_', '').replace('.', '').replace('-', '') == '' or
        safe_name.startswith('_') and len(safe_name.replace('_', '')) < 3):
        
        if video_info and video_info.get('title'):
            # 動画タイトルからファイル名生成
            title = video_info['title']
            
            # 日本語対応のクリーンアップ
            clean_title = re.sub(r'[<>:"/\\|?*]', '', title)
            clean_title = clean_title.strip('. ')[:50]  # 50文字制限
            
            # 拡張子取得
            path = Path(filename)
            suffix = path.suffix or '.mp4'
            
            return sanitize_filename(clean_title + suffix)
    
    return safe_name

def get_safe_filename_with_fallback(original_filename: str, video_info: Dict[str, Any] = None) -> str:
    """
    日本語ファイル名対応（フォールバック機能付き）
    """
    try:
        # まず動画情報を使った生成を試行
        if video_info:
            safe_name = sanitize_filename_with_info(original_filename, video_info)
        else:
            safe_name = sanitize_filename(original_filename)
        
        # 結果が極端に短くなった場合のフォールバック
        if (len(safe_name) < 5 or 
            safe_name.replace('_', '').replace('.', '').replace('-', '') == ''):
            
            # フォールバック1: タイトルベース
            if video_info and video_info.get('title'):
                title_based = create_filename_from_title(video_info['title'], original_filename)
                if title_based:
                    return title_based
            
            # フォールバック2: タイムスタンプ付きファイル名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = Path(original_filename)
            return f"video_{timestamp}{path.suffix or '.mp4'}"
        
        return safe_name
        
    except Exception as e:
        # エラー時の最終フォールバック
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"video_{timestamp}.mp4"

def create_filename_from_title(title: str, original_filename: str = "") -> Optional[str]:
    """
    動画タイトルから安全なファイル名を作成
    """
    if not title:
        return None
    
    # タイトルをクリーンアップ
    clean_title = re.sub(r'[<>:"/\\|?*]', '', title)
    clean_title = clean_title.strip('. ')
    
    # 長すぎる場合は切り詰め
    if len(clean_title.encode('utf-8')) > 100:  # 100バイト制限
        clean_title = limit_filename_bytes(clean_title, 100)
    
    # 拡張子取得
    path = Path(original_filename)
    suffix = path.suffix or '.mp4'
    
    return sanitize_filename(clean_title + suffix)

def generate_unique_filename(base_filename: str, storage_path: str) -> str:
    """
    重複しないユニークなファイル名を生成
    """
    path = Path(base_filename)
    stem = path.stem
    suffix = path.suffix
    
    counter = 1
    unique_filename = base_filename
    
    while Path(storage_path, unique_filename).exists():
        unique_filename = f"{stem}_{counter}{suffix}"
        counter += 1
        
        # 無限ループ防止
        if counter > 1000:
            # ハッシュベースのユニーク名
            hash_suffix = hashlib.md5(f"{stem}_{datetime.now().isoformat()}".encode()).hexdigest()[:8]
            unique_filename = f"{stem}_{hash_suffix}{suffix}"
            break
    
    return unique_filename

# =============================================================================
# URL処理関数
# =============================================================================

def sanitize_url(url: str) -> str:
    """
    URLをサニタイズして安全な形式にする
    """
    if not url:
        return ""
    
    try:
        # URLをパース
        parsed = urlparse(url.strip())
        
        # 基本的なURLバリデーション
        if not parsed.scheme or not parsed.netloc:
            return ""
        
        # 許可されたスキーム
        allowed_schemes = ['http', 'https']
        if parsed.scheme.lower() not in allowed_schemes:
            return ""
        
        # URLを再構築（危険な文字を除去）
        safe_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        # クエリパラメータがある場合は追加
        if parsed.query:
            safe_url += f"?{parsed.query}"
        
        # フラグメントがある場合は追加
        if parsed.fragment:
            safe_url += f"#{parsed.fragment}"
        
        return safe_url
        
    except Exception as e:
        logger.warning(f"URL sanitization error: {e}")
        return ""

def is_valid_url(url: str) -> bool:
    """
    URLの妥当性をチェック
    """
    try:
        url_pattern = re.compile(
            r'^https?://'  # http:// または https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # ドメイン
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
            r'(?::\d+)?'  # ポート番号
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        return url_pattern.match(url) is not None
    except:
        return False

def extract_video_id(url: str) -> Optional[str]:
    """
    URLから動画IDを抽出
    """
    try:
        # YouTube
        youtube_patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/.*[?&]v=([a-zA-Z0-9_-]{11})'
        ]
        
        for pattern in youtube_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # ニコニコ動画
        niconico_pattern = r'nicovideo\.jp/watch/(sm\d+|so\d+|nm\d+)'
        match = re.search(niconico_pattern, url)
        if match:
            return match.group(1)
        
        return None
    except:
        return None

def get_domain_from_url(url: str) -> Optional[str]:
    """
    URLからドメイン名を抽出
    """
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except:
        return None

def generate_cache_key(*args, **kwargs) -> str:
    """
    キャッシュ用のユニークキーを生成
    
    Args:
        *args: キーの構成要素（任意の数）
        **kwargs: 追加のキーワード引数
        
    Returns:
        str: SHA-256ハッシュベースのユニークキー
    """
    try:
        import hashlib
        import json
        
        # 引数を文字列に変換してソート
        key_components = []
        
        # 位置引数を追加
        for arg in args:
            if isinstance(arg, (dict, list)):
                key_components.append(json.dumps(arg, sort_keys=True, ensure_ascii=False))
            else:
                key_components.append(str(arg))
        
        # キーワード引数を追加（ソート済み）
        for key in sorted(kwargs.keys()):
            value = kwargs[key]
            if isinstance(value, (dict, list)):
                key_components.append(f"{key}:{json.dumps(value, sort_keys=True, ensure_ascii=False)}")
            else:
                key_components.append(f"{key}:{str(value)}")
        
        # 全要素を結合
        key_string = ":".join(key_components)
        
        # SHA-256ハッシュ生成
        hash_key = hashlib.sha256(key_string.encode('utf-8')).hexdigest()
        
        return f"cache:{hash_key}"
        
    except Exception as e:
        logger.warning(f"Cache key generation failed: {e}")
        # フォールバック: 簡易ハッシュ
        import hashlib
        fallback_key = str(args) + str(kwargs)
        return f"cache:{hashlib.md5(fallback_key.encode()).hexdigest()}"

def generate_simple_cache_key(key_base: str, salt: str = "") -> str:
    """
    シンプルなキャッシュキー生成（高速版）
    
    Args:
        key_base: ベースとなるキー文字列
        salt: 任意のソルト文字列
        
    Returns:
        str: ハッシュベースのキー
    """
    try:
        import hashlib
        
        key_str = f"{key_base}:{salt}" if salt else key_base
        hash_key = hashlib.sha256(key_str.encode('utf-8')).hexdigest()[:16]  # 短縮版
        
        return f"cache:{hash_key}"
        
    except Exception:
        # エラー時のフォールバック
        return f"cache:{key_base}:{salt}"

def generate_url_cache_key(url: str, options: Dict[str, Any] = None) -> str:
    """
    URL用キャッシュキー生成
    
    Args:
        url: 対象URL
        options: ダウンロードオプション
        
    Returns:
        str: URL専用のキャッシュキー
    """
    try:
        import hashlib
        
        # URLを正規化
        normalized_url = sanitize_url(url)
        
        # オプション文字列化
        options_str = ""
        if options:
            sorted_options = sorted(options.items())
            options_str = ":".join(f"{k}={v}" for k, v in sorted_options)
        
        # キー文字列生成
        key_string = f"url:{normalized_url}:options:{options_str}"
        
        # ハッシュ化
        hash_key = hashlib.sha256(key_string.encode('utf-8')).hexdigest()[:12]
        
        return f"video_cache:{hash_key}"
        
    except Exception:
        # フォールバック
        return f"video_cache:{url.replace('/', '_').replace(':', '_')}"

def generate_job_cache_key(job_id: str, job_type: str = "download") -> str:
    """
    ジョブ用キャッシュキー生成
    
    Args:
        job_id: ジョブID
        job_type: ジョブタイプ
        
    Returns:
        str: ジョブ専用のキャッシュキー
    """
    return f"job:{job_type}:{job_id}"


# =============================================================================
# ネットワーク・IP処理関数
# =============================================================================

def get_client_ip(request) -> str:
    """
    リクエストからクライアントIPアドレスを取得
    
    Args:
        request: FastAPI Request オブジェクト
        
    Returns:
        str: クライアントのIPアドレス
    """
    # X-Forwarded-For ヘッダーをチェック（プロキシ・ロードバランサー対応）
    x_forwarded_for = request.headers.get('x-forwarded-for')
    
    if x_forwarded_for:
        # 複数のIPがある場合、最初のIPを取得（実際のクライアントIP）
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        # 直接接続の場合
        ip = getattr(request.client, 'host', '127.0.0.1') if request.client else '127.0.0.1'
    
    return ip

def get_client_ip_advanced(request) -> str:
    """
    高度なクライアントIP検出（複数のヘッダーをチェック）
    
    Args:
        request: FastAPI Request オブジェクト
        
    Returns:
        str: クライアントのIPアドレス
    """
    # 確認するヘッダーの優先順位リスト
    headers_to_check = [
        'x-forwarded-for',
        'x-real-ip',
        'x-client-ip',
        'cf-connecting-ip',  # Cloudflare
        'fastly-client-ip',  # Fastly
        'true-client-ip',    # Akamai
        'x-cluster-client-ip'
    ]
    
    # 各ヘッダーをチェック
    for header in headers_to_check:
        ip = request.headers.get(header)
        if ip:
            # 複数のIPがある場合、最初のものを使用
            if ',' in ip:
                ip = ip.split(',')[0].strip()
            
            # プライベートIPでない場合は採用
            if not _is_private_ip(ip):
                return ip
    
    # フォールバック: 直接接続のIP
    return getattr(request.client, 'host', '127.0.0.1') if request.client else '127.0.0.1'

def _is_private_ip(ip: str) -> bool:
    """
    プライベートIPアドレスかどうかをチェック
    """
    try:
        private_ranges = [
            '10.',
            '172.16.', '172.17.', '172.18.', '172.19.', '172.20.',
            '172.21.', '172.22.', '172.23.', '172.24.', '172.25.',
            '172.26.', '172.27.', '172.28.', '172.29.', '172.30.', '172.31.',
            '192.168.',
            '127.',
            '169.254.'  # Link-local
        ]
        
        return any(ip.startswith(prefix) for prefix in private_ranges)
    except:
        return True  # エラー時は安全側に倒す

# =============================================================================
# ファイルサイズ・フォーマット関数
# =============================================================================

def format_file_size(size_bytes: int) -> str:
    """
    ファイルサイズを人間が読みやすい形式に変換
    """
    if size_bytes == 0:
        return "0 B"
    
    try:
        size_names = ["B", "KB", "MB", "GB", "TB"]
        size_bytes = float(size_bytes)
        i = 0
        
        while size_bytes >= 1024.0 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    except:
        return "Unknown"

def format_duration(seconds: int) -> str:
    """
    秒数を時:分:秒の形式に変換
    """
    if not seconds or seconds < 0:
        return "0:00"
    
    try:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    except:
        return "0:00"

# =============================================================================
# ハッシュ・セキュリティ関数
# =============================================================================

def generate_job_id() -> str:
    """
    ジョブIDを生成
    """
    import uuid
    return str(uuid.uuid4())

def generate_secure_hash(data: str, salt: str = None) -> str:
    """
    セキュアなハッシュを生成
    """
    try:
        import hashlib
        import secrets
        
        if salt is None:
            salt = secrets.token_hex(16)
        
        # SHA-256でハッシュ化
        hash_obj = hashlib.sha256()
        hash_obj.update((data + salt).encode('utf-8'))
        
        return hash_obj.hexdigest()
    except:
        # フォールバック
        return hashlib.md5(data.encode()).hexdigest()

def validate_file_hash(file_path: str, expected_hash: str, algorithm: str = 'sha256') -> bool:
    """
    ファイルのハッシュ値を検証
    """
    try:
        import hashlib
        
        hash_func = getattr(hashlib, algorithm)()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_func.update(chunk)
        
        return hash_func.hexdigest() == expected_hash
    except:
        return False

# =============================================================================
# 時間・日付処理関数
# =============================================================================

def get_current_timestamp() -> str:
    """
    現在のタイムスタンプを取得（ISO形式）
    """
    return datetime.utcnow().isoformat()

def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """
    タイムスタンプ文字列をパース
    """
    try:
        return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    except:
        return None

def time_ago(timestamp: datetime) -> str:
    """
    相対時間表記（○○前）を生成
    """
    try:
        now = datetime.utcnow()
        diff = now - timestamp
        
        seconds = int(diff.total_seconds())
        
        if seconds < 60:
            return "たった今"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}分前"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours}時間前"
        else:
            days = seconds // 86400
            return f"{days}日前"
    except:
        return "不明"

# =============================================================================
# データ検証関数
# =============================================================================

def validate_video_url(url: str) -> Dict[str, Any]:
    """
    動画URLの包括的な検証
    """
    result = {
        "valid": False,
        "url": url,
        "domain": None,
        "video_id": None,
        "platform": None,
        "errors": []
    }
    
    try:
        # 基本的なURL検証
        if not is_valid_url(url):
            result["errors"].append("Invalid URL format")
            return result
        
        # ドメイン取得
        domain = get_domain_from_url(url)
        result["domain"] = domain
        
        # プラットフォーム判定
        if domain and 'youtube.com' in domain or 'youtu.be' in domain:
            result["platform"] = "youtube"
        elif domain and 'nicovideo.jp' in domain:
            result["platform"] = "niconico"
        elif domain and 'twitter.com' in domain or 'x.com' in domain:
            result["platform"] = "twitter"
        else:
            result["platform"] = "other"
        
        # 動画ID取得
        video_id = extract_video_id(url)
        result["video_id"] = video_id
        
        if not video_id and result["platform"] in ["youtube", "niconico"]:
            result["errors"].append("Could not extract video ID")
        
        # 検証成功
        if not result["errors"]:
            result["valid"] = True
        
    except Exception as e:
        result["errors"].append(f"Validation error: {str(e)}")
    
    return result

def sanitize_user_input(input_str: str, max_length: int = 1000) -> str:
    """
    ユーザー入力をサニタイズ
    """
    if not input_str:
        return ""
    
    try:
        # 長さ制限
        sanitized = input_str[:max_length]
        
        # 危険な文字を除去
        sanitized = re.sub(r'[<>"\']', '', sanitized)
        
        # 制御文字を除去
        sanitized = ''.join(char for char in sanitized if unicodedata.category(char)[0] != 'C')
        
        # 先頭・末尾の空白を除去
        sanitized = sanitized.strip()
        
        return sanitized
    except:
        return ""

# =============================================================================
# デバッグ・ログ関数
# =============================================================================

def log_function_call(func_name: str, args: tuple = None, kwargs: dict = None):
    """
    関数呼び出しをログに記録
    """
    try:
        logger.debug(f"Function call: {func_name}")
        if args:
            logger.debug(f"  Args: {args}")
        if kwargs:
            logger.debug(f"  Kwargs: {kwargs}")
    except:
        pass

def safe_dict_get(dictionary: dict, keys: list, default=None):
    """
    辞書から安全に値を取得（ネストした辞書対応）
    """
    try:
        result = dictionary
        for key in keys:
            result = result[key]
        return result
    except (KeyError, TypeError):
        return default

# =============================================================================
# キャッシュ・パフォーマンス関数
# =============================================================================

def memoize(func):
    """
    簡単なメモ化デコレータ
    """
    cache = {}
    
    def wrapper(*args, **kwargs):
        key = str(args) + str(sorted(kwargs.items()))
        
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        
        return cache[key]
    
    return wrapper

@memoize
def get_video_platform(url: str) -> str:
    """
    動画プラットフォームを判定（キャッシュ付き）
    """
    domain = get_domain_from_url(url)
    
    if not domain:
        return "unknown"
    
    domain = domain.lower()
    
    if 'youtube.com' in domain or 'youtu.be' in domain:
        return "youtube"
    elif 'nicovideo.jp' in domain:
        return "niconico"
    elif 'twitter.com' in domain or 'x.com' in domain:
        return "twitter"
    elif 'tiktok.com' in domain:
        return "tiktok"
    elif 'instagram.com' in domain:
        return "instagram"
    else:
        return "other"
