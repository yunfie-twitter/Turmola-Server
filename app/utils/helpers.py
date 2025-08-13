import re
import hashlib
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import Dict, Any

def sanitize_filename(filename: str) -> str:
    """ファイル名を安全な形式に変換"""
    
    # 特殊文字を全角に変換
    replacements = {
        '/': '／',
        '\\': '＼',
        ':': '：',
        '*': '＊',
        '?': '？',
        '"': '"',
        '<': '＜',
        '>': '＞',
        '|': '｜'
    }
    
    safe_filename = filename
    for char, replacement in replacements.items():
        safe_filename = safe_filename.replace(char, replacement)
    
    # 連続するスペースを単一に
    safe_filename = re.sub(r'\s+', ' ', safe_filename)
    
    # 先頭・末尾のスペース除去
    safe_filename = safe_filename.strip()
    
    # 長すぎる場合は切り詰め
    if len(safe_filename) > 200:
        name, ext = safe_filename.rsplit('.', 1) if '.' in safe_filename else (safe_filename, '')
        max_name_length = 200 - len(ext) - 1
        safe_filename = name[:max_name_length] + ('.' + ext if ext else '')
    
    return safe_filename

def sanitize_url(url: str) -> str:
    """URLから追跡パラメータを除去"""
    
    # 除去するパラメータリスト
    tracking_params = {
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'fbclid', 'gclid', 'msclkid', '_ga', 'ref', 'source'
    }
    
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    
    # 追跡パラメータを除去
    clean_params = {
        key: value for key, value in query_params.items()
        if key not in tracking_params
    }
    
    # URLを再構築
    clean_query = urlencode(clean_params, doseq=True)
    clean_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        clean_query,
        ''  # fragment除去
    ))
    
    return clean_url

def generate_cache_key(url: str, options: Dict[str, Any]) -> str:
    """URLとオプションからキャッシュキーを生成"""
    
    # 重要なオプションのみ考慮
    key_options = {
        'quality': options.get('quality', 'best'),
        'audio_only': options.get('audio_only', False),
        'format_id': options.get('format_id'),
        'subtitles': options.get('subtitles', False),
        'subtitle_lang': options.get('subtitle_lang', 'ja')
    }
    
    # ハッシュ生成
    key_string = f"{url}:{str(sorted(key_options.items()))}"
    hash_object = hashlib.md5(key_string.encode())
    
    return f"download:{hash_object.hexdigest()}"

def format_filesize(bytes_size: int) -> str:
    """ファイルサイズを人間が読みやすい形式に変換"""
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    
    return f"{bytes_size:.1f} PB"

def format_duration(seconds: int) -> str:
    """秒数を時:分:秒形式に変換"""
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"

def validate_url(url: str) -> bool:
    """URLの妥当性を確認"""
    
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    except:
        return False

def extract_domain(url: str) -> str:
    """URLからドメインを抽出"""
    
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except:
        return ""

def is_supported_site(url: str) -> bool:
    """対応サイトかどうか確認"""
    
    supported_domains = {
        'youtube.com', 'youtu.be', 'www.youtube.com',
        'nicovideo.jp', 'www.nicovideo.jp',
        'vimeo.com', 'www.vimeo.com',
        'dailymotion.com', 'www.dailymotion.com',
        'twitch.tv', 'www.twitch.tv'
    }
    
    domain = extract_domain(url)
    return domain in supported_domains

def get_client_ip(request) -> str:
    """クライアントIPアドレスを取得"""
    
    # プロキシ経由の場合のヘッダーを確認
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        # 最初のIPアドレスを取得
        return forwarded_for.split(',')[0].strip()
    
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip
    
    # デフォルト
    return request.client.host if request.client else "unknown"

def generate_cache_key(url: str, options: Dict[str, Any]) -> str:
    """URLとオプションからキャッシュキーを生成（JSON安全版）"""
    
    # 重要なオプションのみ考慮（すべて基本型）
    key_options = {
        'quality': options.get('quality', 'best'),
        'audio_only': options.get('audio_only', False),
        'format_id': options.get('format_id'),
        'subtitles': options.get('subtitles', False),
        'subtitle_lang': options.get('subtitle_lang', 'ja')
    }
    
    # Noneを除去
    key_options = {k: v for k, v in key_options.items() if v is not None}
    
    # ハッシュ生成
    key_string = f"{url}:{str(sorted(key_options.items()))}"
    hash_object = hashlib.md5(key_string.encode())
    
    return f"download:{hash_object.hexdigest()}"
