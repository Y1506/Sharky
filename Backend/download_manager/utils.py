import hashlib
import unicodedata
import shutil
import subprocess
import requests
from pathlib import Path
from urllib.parse import urlparse
from functools import lru_cache
from typing import Tuple, Optional, Union


def format_file_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"

def format_speed(bytes_per_second: float) -> str:
    if bytes_per_second <= 0:
        return "0 B/s"
    for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
        if bytes_per_second < 1024.0:
            return f"{bytes_per_second:.1f} {unit}"
        bytes_per_second /= 1024.0
    return f"{bytes_per_second:.1f} TB/s"

def format_time(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"

def sanitize_filename(filename: str) -> str:
    filename = unicodedata.normalize('NFC', filename)
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    filename = ''.join(c for c in filename if ord(c) >= 32)
    filename = filename.rstrip('. ')
    if len(filename) > 200:
        filename = filename[:200]
    return filename or "download"

def validate_url(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if len(url) < 8 or len(url) > 2000:
        return False
    if not url.startswith(('http://', 'https://', 'magnet:')):
        return False
    if any(ord(c) < 32 for c in url if c != '\n' and c != '\t'):
        return False
    try:
        if url.startswith('magnet:'):
            return 'xt=urn:btih:' in url
        else:
            parsed = urlparse(url)
            return bool(parsed.netloc and '.' in parsed.netloc)
    except Exception:
        return False

def detect_url_type(url: str) -> str:
    url_lower = url.lower()
    if url.startswith('magnet:') or url_lower.endswith('.torrent'):
        return "torrent"
    video_sites = ['youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com', 'twitch.tv', 'facebook.com', 'instagram.com', 'tiktok.com']
    if any(site in url_lower for site in video_sites):
        return "video"
    return "file"

@lru_cache(maxsize=1)
def check_ffmpeg() -> Tuple[bool, str]:
    for cmd in ['ffmpeg', 'ffmpeg.exe', 'ffmpeg.EXE']:
        ffmpeg_path = shutil.which(cmd)
        if ffmpeg_path:
            try:
                subprocess.run([ffmpeg_path, '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3, check=True)
                return True, ffmpeg_path
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                continue
    common_paths = [
        r'C:\ffmpeg\bin\ffmpeg.exe',
        r'C:\Dependencies\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
        '/usr/bin/ffmpeg',
        '/usr/local/bin/ffmpeg',
    ]
    for cmd in common_paths:
        try:
            subprocess.run([cmd, '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3, check=True)
            return True, cmd
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return False, ""

def test_connection(url: str = "https://www.google.com", timeout: int = 5) -> bool:
    try:
        response = requests.head(url, timeout=timeout)
        return response.status_code < 400
    except Exception:
        return False

def compute_file_hash(file_path: Union[str, Path], algorithm: str = "sha256") -> str:
    """Compute cryptographic hash of a file in chunks."""
    h = hashlib.new(algorithm.lower())
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(path, "rb") as f:
        while chunk := f.read(1048576):  # 1MB chunks
            h.update(chunk)
    return h.hexdigest().lower()

def verify_file_hash(file_path: Union[str, Path], expected_hash: str, algorithm: str = "sha256") -> bool:
    """Verify that file hash matches expected hash."""
    if not expected_hash:
        return True
    try:
        actual = compute_file_hash(file_path, algorithm)
        return actual.strip().lower() == expected_hash.strip().lower()
    except Exception:
        return False

