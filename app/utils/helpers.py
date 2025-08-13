"""
ユーティリティ関数（日本語ファイル名完全対応版）
"""

import re
import unicodedata
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

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

def format_file_size(size_bytes: int) -> str:
    """
    ファイルサイズを人間が読みやすい形式に変換
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    size_bytes = float(size_bytes)
    i = 0
    
    while size_bytes >= 1024.0 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def is_valid_url(url: str) -> bool:
    """
    URLの妥当性をチェック
    """
    import re
    url_pattern = re.compile(
        r'^https?://'  # http:// または https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # ドメイン
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
        r'(?::\d+)?'  # ポート番号
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return url_pattern.match(url) is not None

def extract_video_id(url: str) -> Optional[str]:
    """
    URLから動画IDを抽出
    """
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
