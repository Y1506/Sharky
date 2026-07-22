#!/usr/bin/env python3

import asyncio
import glob
import json
import logging
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import unicodedata
import keyboard
import pickle
import psutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

try:
    import requests
    import yt_dlp
    from qbittorrentapi import Client as qBittorrentClient
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    import click
    import xmlrpc.client
except ImportError as e:
    print(f"Missing required dependency: {e}")
    print("Install with: pip install yt-dlp requests qbittorrent-api rich click keyboard psutil")
    sys.exit(1)

console = Console()


@dataclass
class Config:
    BASEDIR: Path = field(default_factory=lambda: Path('../downloads'))
    VIDEODIR: Path = field(init=False)
    AUDIODIR: Path = field(init=False)
    FILESDIR: Path = field(init=False)
    TORRENTSDIR: Path = field(init=False)
    DATABASEFILE: Path = field(init=False)
    LOGFILE: Path = field(init=False)
    SETTINGSFILE: Path = field(init=False)
    MAXRETRIES: int = 2
    CONCURRENTDOWNLOADS: int = 10
    TIMEOUT: int = 300
    CONNECTIONTIMEOUT: int = 30
    RETRYDELAY: int = 0.2
    CHUNKSIZE: int = 4194304
    MAXCONNECTIONS: int = 16
    BUFFER_SIZE: int = 33554432
    DOWNLOAD_SPEED_LIMIT: int = 0
    QBITTORRENT_HOST: str = "http://localhost:8080"
    QBITTORRENT_USERNAME: str = "admin"
    QBITTORRENT_PASSWORD: str = "adminadmin"
    ARIA2C_RPC_PORT: int = 6800
    ARIA2C_SECRET: str = "aria2secret"
    ARIA2C_MAX_CONNECTIONS: int = 16
    ARIA2C_SPLIT: int = 16
    ARIA2C_MIN_SPLIT_SIZE: str = "1M"
    ARIA2C_MAX_CONCURRENT_DOWNLOADS: int = 2
    ARIA2C_PIECE_LENGTH: str = "1M"
    ARIA2C_DISK_CACHE: str = "512M"
    ARIA2C_FILE_ALLOCATION: str = "none"
    ARIA2C_CONTINUE: bool = True
    STATE_FILE: Path = field(init=False)
    PAUSE_HOTKEY: str = "ctrl+shift+p"
    RESUME_HOTKEY: str = "ctrl+shift+r"
    qualityoptions: Optional[List[Tuple[str, str]]] = None

    def __post_init__(self):
        self.VIDEODIR = self.BASEDIR / 'videos'
        self.AUDIODIR = self.BASEDIR / 'audio'
        self.FILESDIR = self.BASEDIR / 'files'
        self.TORRENTSDIR = self.BASEDIR / 'torrents'
        self.DATABASEFILE = self.BASEDIR / 'downloads.db'
        self.LOGFILE = self.BASEDIR / 'download_manager.log'
        self.SETTINGSFILE = Path('settings.json')
        self.STATE_FILE = self.BASEDIR / 'download_state.pkl'

        for directory in [self.BASEDIR, self.VIDEODIR, self.AUDIODIR, self.FILESDIR, self.TORRENTSDIR]:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                console.print(f'[red]Warning: Could not create directory {directory}: {e}[/red]')

    def load_settings(self):
        try:
            if self.SETTINGSFILE.exists():
                with open(self.SETTINGSFILE, 'r') as f:
                    settings = json.load(f)

                for key, value in settings.items():
                    if hasattr(self, key.upper()):
                        if key == 'basedir':
                            self.BASEDIR = Path(value)
                            self.__post_init__()
                        else:
                            setattr(self, key.upper(), value)
        except Exception as e:
            console.print(f'[yellow]Warning: Failed to load settings: {e}[/yellow]')

    def save_settings(self):
        try:
            settings = {
                'basedir': str(self.BASEDIR),
                'concurrentdownloads': self.CONCURRENTDOWNLOADS,
                'aria2c_rpc_port': self.ARIA2C_RPC_PORT,
                'aria2c_secret': self.ARIA2C_SECRET,
                'qbittorrent_host': self.QBITTORRENT_HOST,
                'qbittorrent_username': self.QBITTORRENT_USERNAME,
                'qbittorrent_password': self.QBITTORRENT_PASSWORD,
            }

            with open(self.SETTINGSFILE, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            console.print(f'[yellow]Warning: Failed to save settings: {e}[/yellow]')

    def save_state(self, state_data: dict):
        try:
            with open(self.STATE_FILE, 'wb') as f:
                pickle.dump(state_data, f)
        except Exception as e:
            console.print(f'[yellow]Warning: Failed to save state: {e}[/yellow]')

    def load_state(self) -> dict:
        try:
            if self.STATE_FILE.exists():
                with open(self.STATE_FILE, 'rb') as f:
                    return pickle.load(f)
        except Exception as e:
            console.print(f'[yellow]Warning: Failed to load state: {e}[/yellow]')
        return {}

    @property
    def QUALITY_OPTIONS(self) -> List[Tuple[str, str]]:
        if self.qualityoptions is None:
            self.qualityoptions = [
                ('4K (2160p)', 'bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/best[height<=2160]'),
                ('1440p (2K)', 'bestvideo[height<=1440][ext=mp4]+bestaudio[ext=m4a]/best[height<=1440]'),
                ('1080p60 High Bitrate',
                 'bestvideo[height<=1080][fps>=50][tbr>=3000][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080][tbr>=3000][ext=mp4]+bestaudio[ext=m4a]'),
                ('1080p (Full HD)', 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]'),
                ('720p (HD)', 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]'),
                ('480p (SD)', 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]'),
                ('Best Available', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best'),
                ('Audio Only (High Quality)', 'bestaudio[ext=m4a]/bestaudio[abr>=128]/bestaudio'),
                ('Audio Only (Medium Quality)', 'bestaudio[abr<=128][abr>=64]/bestaudio')
            ]
        return self.qualityoptions

    def set_download_directory(self, new_path: str) -> bool:
        try:
            new_base = Path(new_path).resolve()
            new_base.mkdir(parents=True, exist_ok=True)

            self.BASEDIR = new_base
            self.__post_init__()
            self.save_settings()
            return True
        except Exception:
            return False


config = Config()


class Aria2cManager:
    def __init__(self):
        self.process = None
        self.is_running = False
        self.rpc_url = f"http://localhost:{config.ARIA2C_RPC_PORT}/rpc"
        self.server = None
        self.logger = None

    def set_logger(self, logger):
        self.logger = logger

    def find_aria2c(self) -> Optional[str]:
        import shutil
        for cmd in ['aria2c', 'aria2c.exe']:
            path = shutil.which(cmd)
            if path:
                return path
        common_paths = [
            r'C:\Program Files\aria2\aria2c.exe',
            r'C:\Program Files (x86)\aria2\aria2c.exe',
            r'C:\aria2\aria2c.exe',
            '/usr/bin/aria2c',
            '/usr/local/bin/aria2c',
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
        return None

    def is_port_in_use(self, port: int) -> bool:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0

    def start(self) -> bool:
        if self.is_running:
            return True
        if self.is_port_in_use(config.ARIA2C_RPC_PORT):
            if self.test_connection():
                console.print(f"[green]* aria2c RPC already running on port {config.ARIA2C_RPC_PORT}[/green]")
                self.is_running = True
                return True
            else:
                console.print(
                    f"[yellow]Port {config.ARIA2C_RPC_PORT} is in use but not responding to aria2c RPC[/yellow]")
                return False
        aria2c_path = self.find_aria2c()
        if not aria2c_path:
            console.print("[yellow]aria2c executable not found. Install aria2c for maximum download speed.[/yellow]")
            console.print("[dim]Download from: https://github.com/aria2/aria2/releases[/dim]")
            return False
        console.print(f"[blue]Starting aria2c RPC server on port {config.ARIA2C_RPC_PORT}...[/blue]")
        try:
            cmd = [
                aria2c_path,
                '--enable-rpc',
                f'--rpc-listen-port={config.ARIA2C_RPC_PORT}',
                f'--rpc-secret={config.ARIA2C_SECRET}',
                '--rpc-listen-all=false',
                f'--max-connection-per-server={config.ARIA2C_MAX_CONNECTIONS}',
                f'--split={config.ARIA2C_SPLIT}',
                f'--min-split-size={config.ARIA2C_MIN_SPLIT_SIZE}',
                f'--max-concurrent-downloads={config.ARIA2C_MAX_CONCURRENT_DOWNLOADS}',
                f'--piece-length={config.ARIA2C_PIECE_LENGTH}',
                f'--disk-cache={config.ARIA2C_DISK_CACHE}',
                f'--file-allocation={config.ARIA2C_FILE_ALLOCATION}',
                '--continue=true',
                '--max-tries=20',
                '--retry-wait=0',
                '--timeout=30',
                '--connect-timeout=10',
                '--bt-request-peer-speed-limit=0',
                '--max-overall-download-limit=0',
                '--max-download-limit=0',
                '--max-upload-limit=0',
                '--lowest-speed-limit=0',
                '--max-file-not-found=20',
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                '--enable-http-keep-alive=true',
                '--enable-http-pipelining=true',
                '--http-accept-gzip=true',
                '--enable-mmap=true',
                '--max-mmap-limit=9223372036854775807',
                '--stream-piece-selector=inorder',
                '--uri-selector=inorder',
                '--optimize-concurrent-downloads=true',
                '--auto-file-renaming=false',
                '--allow-overwrite=true',
                '--allow-piece-length-change=true',
                '--always-resume=false',
                '--async-dns=true',
                '--async-dns-server=8.8.8.8,8.8.4.4',
                '--conditional-get=false',
                '--enable-color=false',
                '--reuse-uri=true',
                '--max-resume-failure-tries=0',
                '--remote-time=false',
                '--realtime-chunk-checksum=false',
                '--check-certificate=false',
                '--disable-ipv6=false',
                '--enable-dht=false',
                '--enable-peer-exchange=false',
                '--follow-metalink=false',
                '--metalink-preferred-protocol=http',
                '--bt-enable-lpd=false',
                '--bt-max-peers=0',
                '--bt-stop-timeout=0',
                '--seed-time=0',
                '--seed-ratio=0.0',
                '--log-level=error',
                '--console-log-level=error',
                '--summary-interval=0',
                '--download-result=hide',
                '--quiet=true',
            ]
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    preexec_fn=os.setsid if hasattr(os, 'setsid') else None
                )
            time.sleep(3)
            if self.test_connection():
                self.is_running = True
                console.print("[green]* aria2c RPC server started successfully[/green]")
                if self.logger:
                    self.logger.info("aria2c RPC server started")
                return True
            else:
                console.print("[red]X aria2c RPC server failed to start[/red]")
                if self.process:
                    stdout, stderr = self.process.communicate(timeout=1)
                    if stderr:
                        console.print(f"[red]Error: {stderr.decode('utf-8', errors='ignore')}[/red]")
                self.stop()
                return False
        except Exception as e:
            console.print(f"[red]X Failed to start aria2c: {e}[/red]")
            if self.logger:
                self.logger.error(f"Failed to start aria2c: {e}")
            return False

    def test_connection(self) -> bool:
        try:
            self.server = xmlrpc.client.ServerProxy(self.rpc_url)
            result = self.server.aria2.getVersion(f"token:{config.ARIA2C_SECRET}")
            return 'version' in result
        except Exception:
            self.server = None
            return False

    def stop(self):
        if self.process:
            try:
                if self.server:
                    try:
                        self.server.aria2.shutdown(f"token:{config.ARIA2C_SECRET}")
                        time.sleep(1)
                    except Exception:
                        pass
                if self.process.poll() is None:
                    self.process.terminate()
                    time.sleep(1)
                    if self.process.poll() is None:
                        self.process.kill()
                if self.logger:
                    self.logger.info("aria2c RPC server stopped")
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error stopping aria2c: {e}")
            finally:
                self.process = None
                self.server = None
                self.is_running = False


aria2c_manager = Aria2cManager()


class NetworkMonitor:
    def __init__(self):
        self.download_speed = 0.0
        self.upload_speed = 0.0
        self.monitoring = False
        self._thread = None
        self._lock = threading.Lock()
        self.speed_history = []

    def start(self):
        if self.monitoring:
            return
        self.monitoring = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.monitoring = False
        if self._thread:
            self._thread.join(timeout=2)

    def _monitor_loop(self):
        try:
            old_value = psutil.net_io_counters()
            old_time = time.time()
            while self.monitoring:
                time.sleep(0.5)
                new_value = psutil.net_io_counters()
                new_time = time.time()
                time_diff = new_time - old_time
                if time_diff > 0:
                    download_diff = new_value.bytes_recv - old_value.bytes_recv
                    upload_diff = new_value.bytes_sent - old_value.bytes_sent
                    instant_download = download_diff / time_diff
                    instant_upload = upload_diff / time_diff
                    with self._lock:
                        self.speed_history.append((instant_download, instant_upload))
                        if len(self.speed_history) > 3:
                            self.speed_history.pop(0)
                        if self.speed_history:
                            avg_down = sum(s[0] for s in self.speed_history) / len(self.speed_history)
                            avg_up = sum(s[1] for s in self.speed_history) / len(self.speed_history)
                            self.download_speed = avg_down
                            self.upload_speed = avg_up
                old_value = new_value
                old_time = new_time
        except Exception:
            pass

    def get_speeds(self) -> Dict[str, Union[str, float]]:
        with self._lock:
            return {
                'download': format_speed(self.download_speed),
                'upload': format_speed(self.upload_speed),
                'download_bytes': self.download_speed,
                'upload_bytes': self.upload_speed
            }


network_monitor = NetworkMonitor()


class ProgressDisplayManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._downloads_display = {}
        self._last_full_update = 0
        self._update_interval = 1.0

    def update_progress(self, item_id: int, message: str):
        with self._lock:
            self._downloads_display[item_id] = message
            current_time = time.time()
            if current_time - self._last_full_update >= self._update_interval:
                self._display_all()
                self._last_full_update = current_time

    def remove_download(self, item_id: int):
        with self._lock:
            self._downloads_display.pop(item_id, None)
            if self._downloads_display:
                self._display_all()
            else:
                sys.stdout.write("\r" + " " * 150 + "\r")
                sys.stdout.flush()

    def _display_all(self):
        if not self._downloads_display:
            return
        output = "\r" + " | ".join(self._downloads_display.values())
        sys.stdout.write(output)
        sys.stdout.flush()


progress_display = ProgressDisplayManager()


@lru_cache(maxsize=1)
def check_ffmpeg() -> Tuple[bool, str]:
    import shutil
    for cmd in ['ffmpeg', 'ffmpeg.exe', 'ffmpeg.EXE']:
        ffmpeg_path = shutil.which(cmd)
        if ffmpeg_path:
            try:
                result = subprocess.run([ffmpeg_path, '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        timeout=3, check=True)
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
            result = subprocess.run([cmd, '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3,
                                    check=True)
            return True, cmd
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return False, ""


def check_qbittorrent() -> bool:
    try:
        qb = qBittorrentClient(host=config.QBITTORRENT_HOST, username=config.QBITTORRENT_USERNAME,
                               password=config.QBITTORRENT_PASSWORD)
        qb._session.timeout = 10
        for attempt in range(2):
            try:
                qb.auth_log_in()
                qb.app_version()
                qb.auth_log_out()
                return True
            except Exception:
                if attempt < 1:
                    time.sleep(1)
                    continue
                raise
        return False
    except Exception:
        return False


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
    video_sites = ['youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com', 'twitch.tv', 'facebook.com',
                   'instagram.com', 'tiktok.com']
    if any(site in url_lower for site in video_sites):
        return "video"
    return "file"


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


def test_connection(url: str = "https://www.google.com", timeout: int = 5) -> bool:
    try:
        response = requests.head(url, timeout=timeout)
        return response.status_code < 400
    except Exception:
        return False


@dataclass
class DownloadItem:
    id: Optional[int] = None
    url: str = ""
    title: str = "Unknown"
    download_type: str = "unknown"
    status: str = "pending"
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    downloaded_bytes: int = 0
    upload_bytes: int = 0
    progress: float = 0.0
    download_speed: Optional[str] = None
    upload_speed: Optional[str] = None
    eta: Optional[str] = None
    error_message: Optional[str] = None
    attempts: int = 0
    quality: Optional[str] = None
    include_subtitles: bool = False
    embed_chapters: bool = False
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    seeds: int = 0
    peers: int = 0
    ratio: float = 0.0
    _last_update: float = field(default_factory=time.time)
    _real_start_time: Optional[float] = None
    _real_start_bytes: int = 0
    _last_speed_update: float = field(default_factory=time.time)
    _speed_window: List[float] = field(default_factory=list)

    def should_update_db(self, threshold: float = 0.5) -> bool:
        now = time.time()
        if now - self._last_update >= threshold:
            self._last_update = now
            return True
        return False

    @property
    def progress_percentage(self) -> int:
        return int(min(100, max(0, self.progress)))


class Logger:
    def __init__(self, logfile: Path):
        self.logger = logging.getLogger('DownloadManager')
        self.logger.setLevel(logging.INFO)
        self.setup_handlers(logfile)

    def setup_handlers(self, logfile: Path):
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        try:
            logfile.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(logfile, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
        except Exception as e:
            console.print(f'[yellow]Warning: Failed to set up file logging: {e}[/yellow]')

    def info(self, message: str):
        self.logger.info(message)

    def warning(self, message: str):
        self.logger.warning(message)

    def error(self, message: str):
        self.logger.error(message)

    def debug(self, message: str):
        self.logger.debug(message)


class DatabaseManager:
    def __init__(self, db_file: Optional[Path] = None):
        self.db_file = db_file or config.DATABASEFILE
        self.logger = Logger(config.LOGFILE)
        self._lock = threading.RLock()
        self._init_database()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_file, timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA cache_size=50000")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=268435456")
        return conn

    def _init_database(self):
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute('''
                             CREATE TABLE IF NOT EXISTS downloads
                             (
                                 id
                                 INTEGER
                                 PRIMARY
                                 KEY
                                 AUTOINCREMENT,
                                 url
                                 TEXT
                                 NOT
                                 NULL
                                 UNIQUE,
                                 title
                                 TEXT
                                 DEFAULT
                                 'Unknown',
                                 download_type
                                 TEXT
                                 DEFAULT
                                 'unknown',
                                 status
                                 TEXT
                                 DEFAULT
                                 'pending',
                                 file_path
                                 TEXT,
                                 file_size
                                 INTEGER,
                                 downloaded_bytes
                                 INTEGER
                                 DEFAULT
                                 0,
                                 upload_bytes
                                 INTEGER
                                 DEFAULT
                                 0,
                                 progress
                                 REAL
                                 DEFAULT
                                 0.0,
                                 download_speed
                                 TEXT,
                                 upload_speed
                                 TEXT,
                                 eta
                                 TEXT,
                                 error_message
                                 TEXT,
                                 attempts
                                 INTEGER
                                 DEFAULT
                                 0,
                                 quality
                                 TEXT,
                                 include_subtitles
                                 INTEGER
                                 DEFAULT
                                 0,
                                 embed_chapters
                                 INTEGER
                                 DEFAULT
                                 0,
                                 seeds
                                 INTEGER
                                 DEFAULT
                                 0,
                                 peers
                                 INTEGER
                                 DEFAULT
                                 0,
                                 ratio
                                 REAL
                                 DEFAULT
                                 0.0,
                                 created_at
                                 TIMESTAMP
                                 DEFAULT
                                 CURRENT_TIMESTAMP,
                                 completed_at
                                 TIMESTAMP
                             )
                             ''')
                try:
                    cursor = conn.execute("PRAGMA table_info(downloads)")
                    columns = [row[1] for row in cursor.fetchall()]
                    if 'upload_bytes' not in columns:
                        conn.execute("ALTER TABLE downloads ADD COLUMN upload_bytes INTEGER DEFAULT 0")
                        self.logger.info("Added upload_bytes column to database")
                    if 'upload_speed' not in columns:
                        conn.execute("ALTER TABLE downloads ADD COLUMN upload_speed TEXT")
                        self.logger.info("Added upload_speed column to database")
                    if 'seeds' not in columns:
                        conn.execute("ALTER TABLE downloads ADD COLUMN seeds INTEGER DEFAULT 0")
                        self.logger.info("Added seeds column to database")
                    if 'peers' not in columns:
                        conn.execute("ALTER TABLE downloads ADD COLUMN peers INTEGER DEFAULT 0")
                        self.logger.info("Added peers column to database")
                    if 'ratio' not in columns:
                        conn.execute("ALTER TABLE downloads ADD COLUMN ratio REAL DEFAULT 0.0")
                        self.logger.info("Added ratio column to database")
                except Exception as e:
                    self.logger.warning(f"Migration check failed: {e}")
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_status ON downloads(status)",
                    "CREATE INDEX IF NOT EXISTS idx_type ON downloads(download_type)",
                    "CREATE INDEX IF NOT EXISTS idx_created ON downloads(created_at)",
                ]
                for index in indexes:
                    conn.execute(index)
                conn.commit()
                self.logger.info("Database initialized successfully")
            except Exception as e:
                self.logger.error(f"Database initialization failed: {e}")
                conn.rollback()
                raise
            finally:
                conn.close()

    def add_download(self, item: DownloadItem) -> Optional[int]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute('''
                                      INSERT
                                      OR IGNORE INTO downloads 
                    (url, title, download_type, status, quality, include_subtitles, embed_chapters)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                      ''', (item.url, item.title, item.download_type, item.status, item.quality,
                                            int(item.include_subtitles), int(item.embed_chapters)))
                conn.commit()
                if cursor.rowcount > 0:
                    return cursor.lastrowid
                else:
                    cursor = conn.execute('SELECT id FROM downloads WHERE url = ?', (item.url,))
                    row = cursor.fetchone()
                    return row[0] if row else None
            except Exception as e:
                self.logger.error(f"Failed to add download: {e}")
                conn.rollback()
                return None
            finally:
                conn.close()

    def update_download(self, item: DownloadItem, force: bool = False) -> bool:
        if not item.id or (not force and not item.should_update_db()):
            return False
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute('''
                                      UPDATE downloads
                                      SET title            = ?,
                                          status           = ?,
                                          file_path        = ?,
                                          file_size        = ?,
                                          downloaded_bytes = ?,
                                          upload_bytes     = ?,
                                          progress         = ?,
                                          download_speed   = ?,
                                          upload_speed     = ?,
                                          eta              = ?,
                                          error_message    = ?,
                                          attempts         = ?,
                                          seeds            = ?,
                                          peers            = ?,
                                          ratio            = ?,
                                          completed_at     = ?
                                      WHERE id = ?
                                      ''',
                                      (item.title, item.status, item.file_path, item.file_size, item.downloaded_bytes,
                                       item.upload_bytes, item.progress,
                                       item.download_speed, item.upload_speed, item.eta, item.error_message,
                                       item.attempts, item.seeds, item.peers,
                                       item.ratio, item.completed_at, item.id))
                conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                self.logger.error(f"Failed to update download {item.id}: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()

    def get_downloads_by_status(self, status: str, limit: int = 100) -> List[DownloadItem]:
        conn = self._get_connection()
        try:
            cursor = conn.execute('SELECT * FROM downloads WHERE status = ? ORDER BY created_at DESC LIMIT ?',
                                  (status, limit))
            rows = cursor.fetchall()
            return [item for item in [self._row_to_item(row) for row in rows] if item is not None]
        except Exception as e:
            self.logger.error(f"Failed to get downloads by status: {e}")
            return []
        finally:
            conn.close()

    def get_all_downloads(self, limit: int = 100) -> List[DownloadItem]:
        conn = self._get_connection()
        try:
            cursor = conn.execute('SELECT * FROM downloads ORDER BY created_at DESC LIMIT ?', (limit,))
            rows = cursor.fetchall()
            return [item for item in [self._row_to_item(row) for row in rows] if item is not None]
        except Exception as e:
            self.logger.error(f"Failed to get all downloads: {e}")
            return []
        finally:
            conn.close()

    def get_download_stats(self) -> Dict[str, int]:
        conn = self._get_connection()
        try:
            stats = {}
            cursor = conn.execute('SELECT status, COUNT(*) FROM downloads GROUP BY status')
            for status, count in cursor.fetchall():
                stats[status] = count
            cursor = conn.execute('SELECT COUNT(*) FROM downloads')
            stats['total'] = cursor.fetchone()[0]
            return stats
        except Exception as e:
            self.logger.error(f"Failed to get stats: {e}")
            return {}
        finally:
            conn.close()

    def remove_downloads(self, download_ids: List[int]) -> int:
        if not download_ids:
            return 0
        with self._lock:
            conn = self._get_connection()
            try:
                placeholders = ','.join(['?' for _ in download_ids])
                cursor = conn.execute(f'DELETE FROM downloads WHERE id IN ({placeholders})', download_ids)
                conn.commit()
                return cursor.rowcount
            except Exception as e:
                self.logger.error(f"Failed to remove downloads: {e}")
                conn.rollback()
                return 0
            finally:
                conn.close()

    def clear_completed_downloads(self) -> int:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute("DELETE FROM downloads WHERE status = 'completed'")
                conn.commit()
                return cursor.rowcount
            except Exception as e:
                self.logger.error(f"Failed to clear completed: {e}")
                conn.rollback()
                return 0
            finally:
                conn.close()

    def clear_failed_downloads(self) -> int:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute("DELETE FROM downloads WHERE status = 'failed'")
                conn.commit()
                return cursor.rowcount
            except Exception as e:
                self.logger.error(f"Failed to clear failed: {e}")
                conn.rollback()
                return 0
            finally:
                conn.close()

    def _row_to_item(self, row) -> Optional[DownloadItem]:
        if not row:
            return None
        try:
            return DownloadItem(
                id=row[0], url=row[1], title=row[2], download_type=row[3], status=row[4], file_path=row[5],
                file_size=row[6],
                downloaded_bytes=row[7] or 0, upload_bytes=row[8] or 0, progress=row[9] or 0.0, download_speed=row[10],
                upload_speed=row[11],
                eta=row[12], error_message=row[13], attempts=row[14] or 0, quality=row[15],
                include_subtitles=bool(row[16] if len(row) > 16 else False),
                embed_chapters=bool(row[17] if len(row) > 17 else False),
                seeds=row[18] if len(row) > 18 else 0, peers=row[19] if len(row) > 19 else 0,
                ratio=row[20] if len(row) > 20 else 0.0,
                created_at=row[21] if len(row) > 21 else None, completed_at=row[22] if len(row) > 22 else None
            )
        except Exception as e:
            self.logger.error(f"Failed to convert row to item: {e}")
            return None


class Aria2cDownloader:
    def __init__(self, db_manager: DatabaseManager, shutdown_event: threading.Event, pause_event: threading.Event):
        self.db = db_manager
        self.logger = Logger(config.LOGFILE)
        self.shutdown_event = shutdown_event
        self.pause_event = pause_event
        self.server = aria2c_manager.server
        self.is_available = aria2c_manager.is_running

    def download_file(self, item: DownloadItem) -> bool:
        if not self.is_available or not aria2c_manager.server:
            return False
        try:
            # Check pause before starting
            while not self.pause_event.is_set():
                if self.shutdown_event.is_set():
                    return False
                time.sleep(0.1)

            if item.download_type == "video":
                output_dir = config.VIDEODIR
            else:
                output_dir = config.FILESDIR
            output_dir.mkdir(parents=True, exist_ok=True)
            filename = self._extract_filename(item.url)
            if not filename or filename == "download.bin":
                filename = f"{sanitize_filename(item.title)}.bin"
            file_path = output_dir / filename
            item.file_path = str(file_path)
            options = {
                'dir': str(output_dir), 'out': filename,
                'max-connection-per-server': str(config.ARIA2C_MAX_CONNECTIONS),
                'split': str(config.ARIA2C_SPLIT), 'min-split-size': config.ARIA2C_MIN_SPLIT_SIZE,
                'max-concurrent-downloads': '1',
                'piece-length': config.ARIA2C_PIECE_LENGTH, 'disk-cache': config.ARIA2C_DISK_CACHE,
                'file-allocation': config.ARIA2C_FILE_ALLOCATION,
                'continue': 'true', 'max-tries': '5', 'retry-wait': '2', 'timeout': '60', 'connect-timeout': '30',
                'max-file-not-found': '5',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'referer': '*',
                'enable-http-keep-alive': 'true',
                'enable-http-pipelining': 'true', 'enable-mmap': 'true', 'stream-piece-selector': 'geom',
                'optimize-concurrent-downloads': 'true',
                'max-download-limit': '0', 'lowest-speed-limit': '0', 'max-overall-download-limit': '0',
                'conditional-get': 'true',
                'remote-time': 'true', 'reuse-uri': 'true', 'max-resume-failure-tries': '5',
            }
            gid = aria2c_manager.server.aria2.addUri(f"token:{config.ARIA2C_SECRET}", [item.url], options)
            item.status = "downloading"
            self.db.update_download(item, force=True)
            console.print(f"[blue]Downloading with aria2c (16 connections): {filename}[/blue]")
            return self._monitor_download(item, gid)
        except Exception as e:
            item.status = "failed"
            item.error_message = str(e)[:400]
            self.db.update_download(item, force=True)
            console.print(f"[red]X aria2c download failed: {str(e)}[/red]")
            return False

    def _monitor_download(self, item: DownloadItem, gid: str) -> bool:
        try:
            item._real_start_time = time.time()
            item._real_start_bytes = 0
            last_bytes = 0
            last_time = time.time()
            speed_samples = []
            while not self.shutdown_event.is_set():
                # Check pause frequently
                while not self.pause_event.is_set():
                    if self.shutdown_event.is_set():
                        return False
                    time.sleep(0.1)

                current_time = time.time()
                status = aria2c_manager.server.aria2.tellStatus(
                    f"token:{config.ARIA2C_SECRET}", gid,
                    ['totalLength', 'completedLength', 'downloadSpeed', 'connections', 'status', 'errorMessage']
                )
                if 'totalLength' in status and status['totalLength']:
                    item.file_size = int(status['totalLength'])
                    item.downloaded_bytes = int(status['completedLength'])
                    if item.file_size > 0:
                        item.progress = (item.downloaded_bytes / item.file_size) * 100
                    elapsed = current_time - last_time
                    if elapsed >= 0.5:
                        bytes_diff = item.downloaded_bytes - last_bytes
                        if elapsed > 0 and bytes_diff > 0:
                            instant_speed = bytes_diff / elapsed
                            speed_samples.append(instant_speed)
                            if len(speed_samples) > 3:
                                speed_samples.pop(0)
                            avg_speed = sum(speed_samples) / len(speed_samples)
                            item.download_speed = format_speed(avg_speed)
                            if avg_speed > 0:
                                remaining_bytes = item.file_size - item.downloaded_bytes
                                eta_seconds = int(remaining_bytes / avg_speed)
                                item.eta = format_time(eta_seconds)
                            if item.id:
                                connections = status.get('connections', 0)
                                size_display = ""
                                if item.file_size:
                                    size_display = f" | {format_file_size(item.downloaded_bytes)}/{format_file_size(item.file_size)}"
                                progress_msg = (
                                    f"Download {item.id} (aria2c): {item.title[:35]}... | "
                                    f"{item.progress_percentage}%{size_display} | "
                                    f"{item.download_speed} | "
                                    f"ETA: {item.eta or 'Unknown'} | "
                                    f"Conn: {connections}"
                                )
                                progress_display.update_progress(item.id, progress_msg)
                        last_bytes = item.downloaded_bytes
                        last_time = current_time
                self.db.update_download(item)
                if status['status'] == 'complete':
                    item.status = "completed"
                    item.progress = 100.0
                    item.completed_at = time.strftime('%Y-%m-%d %H:%M:%S')
                    self.db.update_download(item, force=True)
                    if item.id:
                        progress_display.remove_download(item.id)
                    console.print(f"[green]* Download completed: {item.title}[/green]")
                    return True
                if status['status'] == 'error':
                    item.status = "failed"
                    item.error_message = status.get('errorMessage', 'Unknown error')
                    self.db.update_download(item, force=True)
                    if item.id:
                        progress_display.remove_download(item.id)
                    return False
                time.sleep(0.5)
            return False
        except Exception as e:
            item.status = "failed"
            item.error_message = str(e)[:400]
            self.db.update_download(item, force=True)
            if item.id:
                progress_display.remove_download(item.id)
            return False

    def _extract_filename(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            if parsed.path:
                filename = os.path.basename(parsed.path)
                if '?' in filename:
                    filename = filename.split('?')[0]
                if filename and not filename.startswith('.'):
                    return sanitize_filename(filename)
        except Exception:
            pass
        return "download.bin"


class VideoDownloader:
    def __init__(self, db_manager: DatabaseManager, shutdown_event: threading.Event, pause_event: threading.Event):
        self.db = db_manager
        self.logger = Logger(config.LOGFILE)
        self.shutdown_event = shutdown_event
        self.pause_event = pause_event
        self.has_ffmpeg, self.ffmpeg_cmd = check_ffmpeg()

    def download(self, item: DownloadItem, quality: str = "best") -> bool:
        try:
            if self.shutdown_event.is_set():
                return False

            # Check pause before starting
            while not self.pause_event.is_set():
                if self.shutdown_event.is_set():
                    return False
                time.sleep(0.1)

            self._extract_video_info(item)
            is_audio = self._is_audio_only(quality)
            output_dir = config.AUDIODIR if is_audio else config.VIDEODIR
            output_dir.mkdir(parents=True, exist_ok=True)
            if is_audio:
                item.include_subtitles = False
                item.embed_chapters = False
            sanitized_title = sanitize_filename(item.title)
            ydl_opts = self._build_ydl_options(quality, output_dir, sanitized_title, item)
            for attempt in range(1, config.MAXRETRIES + 1):
                try:
                    # Check pause before each attempt
                    while not self.pause_event.is_set():
                        if self.shutdown_event.is_set():
                            return False
                        time.sleep(0.1)

                    item.attempts = attempt
                    self.db.update_download(item, force=True)
                    console.print(f"[blue]Downloading: {item.title}[/blue]")
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([item.url])
                    downloaded_file = self._find_downloaded_file(output_dir, sanitized_title, is_audio)
                    if downloaded_file and downloaded_file.exists():
                        item.status = "completed"
                        item.progress = 100.0
                        item.file_path = str(downloaded_file)
                        item.file_size = downloaded_file.stat().st_size
                        item.downloaded_bytes = item.file_size
                        item.completed_at = time.strftime('%Y-%m-%d %H:%M:%S')
                        self.db.update_download(item, force=True)
                        if item.id:
                            progress_display.remove_download(item.id)
                        console.print(f"[green]* Download completed: {item.title}[/green]")
                        if not is_audio and bool(item.include_subtitles) and self.has_ffmpeg:
                            if self._verify_embedded_subtitles(downloaded_file):
                                console.print("[green]* Subtitles successfully embedded[/green]")
                            else:
                                console.print("[yellow]! Warning: Subtitles may not be embedded[/yellow]")
                        self._cleanup_temp_files(output_dir, sanitized_title)
                        if not is_audio and bool(item.include_subtitles) and self.has_ffmpeg:
                            time.sleep(1)
                            self._cleanup_subtitle_files(output_dir, sanitized_title)
                        return True
                except Exception as e:
                    error_msg = str(e)
                    self.logger.error(f"Download attempt {attempt} failed: {error_msg}")
                    if attempt < config.MAXRETRIES:
                        console.print(f"[yellow]Attempt {attempt} failed, retrying in {config.RETRYDELAY}s...[/yellow]")
                        time.sleep(config.RETRYDELAY)
                    else:
                        item.status = "failed"
                        item.error_message = error_msg[:400]
                        self.db.update_download(item, force=True)
                        console.print(f"[red]X Download failed: {error_msg}[/red]")
                        return False
            return False
        except Exception as e:
            item.status = "failed"
            item.error_message = str(e)[:400]
            self.db.update_download(item, force=True)
            console.print(f"[red]X Download failed: {str(e)}[/red]")
            return False

    def _extract_video_info(self, item: DownloadItem):
        try:
            ydl_opts = {'quiet': True, 'extract_flat': True, 'no_warnings': True, 'socket_timeout': 30}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(item.url, download=False)
                if info:
                    if 'entries' in info:
                        entry_count = len([e for e in info.get('entries', []) if e])
                        item.title = f"{info.get('title', 'Playlist')} ({entry_count} videos)"
                    else:
                        item.title = info.get('title', 'Unknown Video')[:100]
                    item.title = sanitize_filename(item.title)
                    self.db.update_download(item, force=True)
        except Exception as e:
            self.logger.debug(f"Info extraction failed: {e}")
            item.title = "Unknown Video"

    def _build_ydl_options(self, quality: str, output_dir: Path, title: str, item: DownloadItem) -> dict:
        is_audio = self._is_audio_only(quality)
        active_count = len([d for d in self.db.get_downloads_by_status("downloading")])
        if active_count >= 8:
            concurrent_fragments = 32
        elif active_count >= 4:
            concurrent_fragments = 64
        else:
            concurrent_fragments = 128

        ydl_opts = {
            'format': self._get_format_string(quality),
            'outtmpl': str(output_dir / f'{title}.%(ext)s'),
            'no_warnings': True,
            'socket_timeout': 60,
            'retries': 10,
            'fragment_retries': 20,
            'file_access_retries': 10,
            'concurrent_fragment_downloads': concurrent_fragments,
            'http_chunk_size': config.CHUNKSIZE,
            'progress_hooks': [lambda d: self._progress_hook(d, item)],
            'no_check_certificate': True,
            'prefer_insecure': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'DNT': '1',
            },
            'sleep_interval': 0,
            'max_sleep_interval': 0,
            'no_color': True,
            'quiet': True,
            'no_progress': True,
            'geo_bypass': True,
            'buffer_size': config.BUFFER_SIZE,
            'source_address': '0.0.0.0',
            'force_generic_extractor': False,
            'extract_flat': False,
            'skip_unavailable_fragments': True,
            'continue': True,
            'overwrites': True,
            'keepvideo': False,
            'postprocessors': [],
        }

        if not is_audio:
            include_subs = bool(item.include_subtitles)
            if include_subs and self.has_ffmpeg:
                ydl_opts['writesubtitles'] = True
                ydl_opts['writeautomaticsub'] = True
                ydl_opts['subtitleslangs'] = ['en', 'en-US', 'en-GB', 'en-AU']
                ydl_opts['subtitlesformat'] = 'best'
                ydl_opts['embedsubtitles'] = True
                ydl_opts['postprocessors'].append({'key': 'FFmpegEmbedSubtitle', 'already_have_subtitle': False})
                console.print("[green]* Subtitles will be embedded[/green]")
            elif include_subs:
                ydl_opts['writesubtitles'] = True
                ydl_opts['writeautomaticsub'] = True
                ydl_opts['subtitleslangs'] = ['en', 'en-US', 'en-GB', 'en-AU']
                ydl_opts['subtitlesformat'] = 'srt'
                console.print("[yellow]! FFmpeg not found. Subtitles saved separately[/yellow]")

            embed_chaps = bool(item.embed_chapters)
            if embed_chaps and self.has_ffmpeg:
                ydl_opts['postprocessors'].append({'key': 'FFmpegMetadata', 'add_chapters': True, 'add_metadata': True})
                ydl_opts['addchapters'] = True
                console.print("[green]* Chapters will be embedded[/green]")

        if self.has_ffmpeg and self.ffmpeg_cmd:
            ydl_opts['ffmpeg_location'] = self.ffmpeg_cmd
            if not is_audio:
                ydl_opts['postprocessors'].insert(0, {'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'})
                ydl_opts['postprocessor_args'] = [
                    '-threads', '0', '-preset', 'ultrafast', '-movflags', '+faststart', '-fflags', '+genpts+igndts',
                    '-avoid_negative_ts', 'make_zero', '-c:v', 'copy', '-c:a', 'copy',
                ]

        return ydl_opts

    def _get_format_string(self, quality: str) -> str:
        if not self.has_ffmpeg:
            format_map = {
                '4K (2160p)': 'best[height<=2160][ext=mp4]',
                '1440p (2K)': 'best[height<=1440][ext=mp4]',
                '1080p60 High Bitrate': 'best[height<=1080][ext=mp4]',
                '1080p (Full HD)': 'best[height<=1080][ext=mp4]',
                '720p (HD)': 'best[height<=720][ext=mp4]',
                '480p (SD)': 'best[height<=480][ext=mp4]',
                'Best Available': 'best[ext=mp4]',
                'Audio Only (High Quality)': 'bestaudio[ext=m4a]/bestaudio',
                'Audio Only (Medium Quality)': 'bestaudio[ext=m4a]/bestaudio',
            }
            return format_map.get(quality, 'best')
        format_map = {
            '4K (2160p)': 'bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/best[height<=2160]',
            '1440p (2K)': 'bestvideo[height<=1440][ext=mp4]+bestaudio[ext=m4a]/best[height<=1440]',
            '1080p60 High Bitrate': 'bestvideo[height<=1080][fps>=50][tbr>=3000][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080][tbr>=3000][ext=mp4]+bestaudio[ext=m4a]',
            '1080p (Full HD)': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]',
            '720p (HD)': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]',
            '480p (SD)': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]',
            'Best Available': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
            'Audio Only (High Quality)': 'bestaudio[ext=m4a]/bestaudio[abr>=128]/bestaudio',
            'Audio Only (Medium Quality)': 'bestaudio[abr<=128][abr>=64]/bestaudio',
        }
        return format_map.get(quality, 'best')

    def _is_audio_only(self, quality: str) -> bool:
        return 'Audio Only' in quality

    def _progress_hook(self, d: dict, item: DownloadItem):
        if d['status'] == 'downloading':
            # Check pause flag frequently
            while not self.pause_event.is_set():
                if self.shutdown_event.is_set():
                    raise Exception("Download cancelled by user")
                time.sleep(0.1)

            current_time = time.time()
            if item._real_start_time is None:
                item._real_start_time = current_time
                item._real_start_bytes = 0
                item._last_speed_update = current_time
                item._speed_window = []
            if 'downloaded_bytes' in d and 'total_bytes' in d:
                item.downloaded_bytes = d['downloaded_bytes']
                item.file_size = d['total_bytes']
                item.progress = (item.downloaded_bytes / item.file_size) * 100
            elif 'downloaded_bytes' in d and 'total_bytes_estimate' in d:
                item.downloaded_bytes = d['downloaded_bytes']
                item.file_size = d['total_bytes_estimate']
                item.progress = (item.downloaded_bytes / item.file_size) * 100
            time_since_update = current_time - item._last_speed_update
            if time_since_update >= 0.5:
                total_elapsed = current_time - item._real_start_time
                if total_elapsed > 0 and item.downloaded_bytes > 0:
                    bytes_since_last = item.downloaded_bytes - item._real_start_bytes
                    instant_speed = bytes_since_last / time_since_update
                    item._speed_window.append(instant_speed)
                    if len(item._speed_window) > 3:
                        item._speed_window.pop(0)
                    avg_speed = sum(item._speed_window) / len(item._speed_window)
                    item.download_speed = format_speed(avg_speed)
                    if item.file_size and avg_speed > 0:
                        remaining_bytes = item.file_size - item.downloaded_bytes
                        eta_seconds = int(remaining_bytes / avg_speed)
                        item.eta = format_time(eta_seconds)
                    if item.id:
                        size_display = ""
                        if item.file_size:
                            size_display = f" | {format_file_size(item.downloaded_bytes)}/{format_file_size(item.file_size)}"
                        progress_msg = (
                            f"Download {item.id}: {item.title[:40]}... | "
                            f"{item.progress_percentage}%{size_display} | "
                            f"{item.download_speed} | "
                            f"ETA: {item.eta or 'Unknown'}"
                        )
                        progress_display.update_progress(item.id, progress_msg)
                    item._last_speed_update = current_time
                    item._real_start_bytes = item.downloaded_bytes
            if item.should_update_db(threshold=1.0):
                self.db.update_download(item)

    def _find_downloaded_file(self, output_dir: Path, title: str, is_audio: bool) -> Optional[Path]:
        extensions = ['.m4a', '.mp3'] if is_audio else ['.mp4', '.mkv', '.webm']
        for ext in extensions:
            file_path = output_dir / f"{title}{ext}"
            if file_path.exists() and file_path.stat().st_size > 0:
                return file_path
        return None

    def _cleanup_temp_files(self, output_dir: Path, title: str):
        try:
            patterns = [f"{title}*.part", f"{title}*.tmp", f"{title}*.f*.*"]
            for pattern in patterns:
                for file_path in glob.glob(str(output_dir / pattern)):
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
        except Exception as e:
            self.logger.debug(f"Cleanup failed: {e}")

    def _cleanup_subtitle_files(self, output_dir: Path, title: str):
        try:
            subtitle_patterns = [
                f"{title}.*.srt", f"{title}.*.vtt", f"{title}.*.ass",
                f"{title}.*.ssa", f"{title}.*.sub", f"{title}.*.sbv",
                f"{title}.en.srt", f"{title}.en.vtt", f"{title}.en-US.srt",
                f"{title}.en-GB.srt", f"{title}.en-AU.srt",
            ]
            removed_count = 0
            for pattern in subtitle_patterns:
                for file_path in glob.glob(str(output_dir / pattern)):
                    try:
                        if file_path.lower().endswith(('.srt', '.vtt', '.ass', '.ssa', '.sub', '.sbv')):
                            os.remove(file_path)
                            removed_count += 1
                            self.logger.debug(f"Removed subtitle file: {file_path}")
                    except Exception as e:
                        self.logger.debug(f"Failed to remove {file_path}: {e}")
            if removed_count > 0:
                self.logger.info(f"Cleaned up {removed_count} subtitle files")
        except Exception as e:
            self.logger.debug(f"Subtitle cleanup failed: {e}")

    def _verify_embedded_subtitles(self, video_file: Path) -> bool:
        try:
            if not self.has_ffmpeg or not self.ffmpeg_cmd:
                return False
            ffprobe_cmd = self.ffmpeg_cmd.replace('ffmpeg', 'ffprobe')
            result = subprocess.run(
                [ffprobe_cmd, '-v', 'error', '-select_streams', 's',
                 '-show_entries', 'stream=codec_type',
                 '-of', 'default=noprint_wrappers=1:nokey=1', str(video_file)],
                capture_output=True,
                text=True,
                timeout=10
            )
            output = result.stdout.strip()
            has_subtitles = 'subtitle' in output.lower() or output.count('\n') > 0
            self.logger.debug(f"Subtitle check output: {output}")
            return has_subtitles
        except Exception as e:
            self.logger.debug(f"Subtitle verification failed: {e}")
            return False


class FileDownloader:
    def __init__(self, db_manager: DatabaseManager, shutdown_event: threading.Event, pause_event: threading.Event):
        self.db = db_manager
        self.logger = Logger(config.LOGFILE)
        self.shutdown_event = shutdown_event
        self.pause_event = pause_event

    def download_file(self, item: DownloadItem) -> bool:
        try:
            if self.shutdown_event.is_set():
                return False

            # Check pause before starting
            while not self.pause_event.is_set():
                if self.shutdown_event.is_set():
                    return False
                time.sleep(0.1)

            config.FILESDIR.mkdir(parents=True, exist_ok=True)
            filename = self._extract_filename(item.url)
            file_path = config.FILESDIR / filename
            item.title = filename
            item.file_path = str(file_path)
            resume_header = {}
            if file_path.exists():
                resume_pos = file_path.stat().st_size
                resume_header = {'Range': f'bytes={resume_pos}-'}
                item.downloaded_bytes = resume_pos
                console.print(f"[yellow]Resuming from {format_file_size(resume_pos)}[/yellow]")
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*', 'Accept-Language': 'en-US,en;q=0.9', 'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive', 'Cache-Control': 'no-cache', 'Pragma': 'no-cache',
            })
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=config.MAXCONNECTIONS, pool_maxsize=config.MAXCONNECTIONS, max_retries=0,
                pool_block=False
            )
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            response = session.get(item.url, stream=True, timeout=config.TIMEOUT, headers=resume_header)
            response.raise_for_status()
            if 'content-length' in response.headers:
                if resume_header:
                    item.file_size = int(response.headers['content-length']) + item.downloaded_bytes
                else:
                    item.file_size = int(response.headers['content-length'])
            item.status = "downloading"
            self.db.update_download(item, force=True)
            console.print(f"[blue]Downloading: {filename}[/blue]")
            mode = 'ab' if resume_header else 'wb'
            start_time = time.time()
            start_bytes = item.downloaded_bytes
            last_update_time = start_time
            with open(file_path, mode, buffering=config.BUFFER_SIZE) as f:
                for chunk in response.iter_content(chunk_size=config.CHUNKSIZE):
                    # Check pause frequently
                    while not self.pause_event.is_set():
                        if self.shutdown_event.is_set():
                            console.print(f"[yellow]Download cancelled: {filename}[/yellow]")
                            return False
                        time.sleep(0.1)

                    if self.shutdown_event.is_set():
                        return False
                    if chunk:
                        f.write(chunk)
                        item.downloaded_bytes += len(chunk)
                        current_time = time.time()
                        time_since_update = current_time - last_update_time
                        if time_since_update >= 1.0 and item.file_size and item.file_size > 0:
                            item.progress = min(100.0, (item.downloaded_bytes / item.file_size) * 100)
                            bytes_since_start = item.downloaded_bytes - start_bytes
                            real_speed = bytes_since_start / (current_time - start_time) if (
                                                                                                        current_time - start_time) > 0 else 0
                            item.download_speed = format_speed(real_speed)
                            if real_speed > 0:
                                remaining_bytes = item.file_size - item.downloaded_bytes
                                eta_seconds = int(remaining_bytes / real_speed)
                                item.eta = format_time(eta_seconds)
                            if item.id:
                                size_display = ""
                                if item.file_size:
                                    size_display = f" | {format_file_size(item.downloaded_bytes)}/{format_file_size(item.file_size)}"
                                progress_msg = (
                                    f"Download {item.id}: {item.title[:40]}... | "
                                    f"{item.progress_percentage}%{size_display} | "
                                    f"{item.download_speed} | "
                                    f"ETA: {item.eta or 'Unknown'}"
                                )
                                progress_display.update_progress(item.id, progress_msg)
                            self.db.update_download(item)
                            last_update_time = current_time
            if file_path.exists() and file_path.stat().st_size > 0:
                item.status = "completed"
                item.progress = 100.0
                item.file_size = file_path.stat().st_size
                item.downloaded_bytes = item.file_size
                item.completed_at = time.strftime('%Y-%m-%d %H:%M:%S')
                self.db.update_download(item, force=True)
                if item.id:
                    progress_display.remove_download(item.id)
                console.print(f"[green]* Download completed: {filename} ({format_file_size(item.file_size)})[/green]")
                return True
            else:
                raise Exception("Downloaded file is missing or empty")
        except Exception as e:
            item.status = "failed"
            item.error_message = str(e)[:400]
            self.db.update_download(item, force=True)
            if item.id:
                progress_display.remove_download(item.id)
            console.print(f"[red]X Download failed: {str(e)}[/red]")
            return False

    def _extract_filename(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            if parsed.path:
                filename = os.path.basename(parsed.path)
                if '?' in filename:
                    filename = filename.split('?')[0]
                if filename and not filename.startswith('.'):
                    return sanitize_filename(filename)
        except Exception:
            pass
        return "download.bin"

        try:
            if self.shutdown_event.is_set():
                return False
            self.pause_event.wait()
            config.FILESDIR.mkdir(parents=True, exist_ok=True)
            filename = self._extract_filename(item.url)
            file_path = config.FILESDIR / filename
            item.title = filename
            item.file_path = str(file_path)
            resume_header = {}
            if file_path.exists():
                resume_pos = file_path.stat().st_size
                resume_header = {'Range': f'bytes={resume_pos}-'}
                item.downloaded_bytes = resume_pos
                console.print(f"[yellow]Resuming from {format_file_size(resume_pos)}[/yellow]")
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*', 'Accept-Language': 'en-US,en;q=0.9', 'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive', 'Cache-Control': 'no-cache', 'Pragma': 'no-cache',
            })
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=config.MAXCONNECTIONS, pool_maxsize=config.MAXCONNECTIONS, max_retries=0,
                pool_block=False
            )
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            response = session.get(item.url, stream=True, timeout=config.TIMEOUT, headers=resume_header)
            response.raise_for_status()
            if 'content-length' in response.headers:
                if resume_header:
                    item.file_size = int(response.headers['content-length']) + item.downloaded_bytes
                else:
                    item.file_size = int(response.headers['content-length'])
            item.status = "downloading"
            self.db.update_download(item, force=True)
            console.print(f"[blue]Downloading: {filename}[/blue]")
            mode = 'ab' if resume_header else 'wb'
            start_time = time.time()
            start_bytes = item.downloaded_bytes
            last_update_time = start_time
            with open(file_path, mode, buffering=config.BUFFER_SIZE) as f:
                for chunk in response.iter_content(chunk_size=config.CHUNKSIZE):
                    # Check pause frequently
                    while not self.pause_event.is_set():
                        if self.shutdown_event.is_set():
                            console.print(f"[yellow]Download cancelled: {filename}[/yellow]")
                            return False
                        time.sleep(0.1)

                    if self.shutdown_event.is_set():
                        return False
                    if chunk:
                        f.write(chunk)
                        item.downloaded_bytes += len(chunk)
                        current_time = time.time()
                        elapsed = current_time - start_time
                        time_since_update = current_time - last_update_time
                        if time_since_update >= 1.0 and item.file_size and item.file_size > 0:
                            item.progress = min(100.0, (item.downloaded_bytes / item.file_size) * 100)
                            bytes_since_start = item.downloaded_bytes - start_bytes
                            real_speed = bytes_since_start / elapsed if elapsed > 0 else 0
                            item.download_speed = format_speed(real_speed)
                            if real_speed > 0:
                                remaining_bytes = item.file_size - item.downloaded_bytes
                                eta_seconds = int(remaining_bytes / real_speed)
                                item.eta = format_time(eta_seconds)
                            if item.id:
                                size_display = ""
                                if item.file_size:
                                    size_display = f" | {format_file_size(item.downloaded_bytes)}/{format_file_size(item.file_size)}"
                                progress_msg = (
                                    f"Download {item.id}: {item.title[:40]}... | "
                                    f"{item.progress_percentage}%{size_display} | "
                                    f"{item.download_speed} | "
                                    f"ETA: {item.eta or 'Unknown'}"
                                )
                                progress_display.update_progress(item.id, progress_msg)
                            self.db.update_download(item)
                            last_update_time = current_time
            if file_path.exists() and file_path.stat().st_size > 0:
                item.status = "completed"
                item.progress = 100.0
                item.file_size = file_path.stat().st_size
                item.downloaded_bytes = item.file_size
                item.completed_at = time.strftime('%Y-%m-%d %H:%M:%S')
                self.db.update_download(item, force=True)
                if item.id:
                    progress_display.remove_download(item.id)
                console.print(f"[green]* Download completed: {filename} ({format_file_size(item.file_size)})[/green]")
                return True
            else:
                raise Exception("Downloaded file is missing or empty")
        except Exception as e:
            item.status = "failed"
            item.error_message = str(e)[:400]
            self.db.update_download(item, force=True)
            if item.id:
                progress_display.remove_download(item.id)
            console.print(f"[red]X Download failed: {str(e)}[/red]")
            return False

    def _extract_filename(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            if parsed.path:
                filename = os.path.basename(parsed.path)
                if '?' in filename:
                    filename = filename.split('?')[0]
                if filename and not filename.startswith('.'):
                    return sanitize_filename(filename)
        except Exception:
            pass
        return "download.bin"


class TorrentDownloader:
    def __init__(self, db_manager: DatabaseManager, shutdown_event: threading.Event, pause_event: threading.Event):
        self.db = db_manager
        self.logger = Logger(config.LOGFILE)
        self.shutdown_event = shutdown_event
        self.pause_event = pause_event
        self.qb_client = None
        self.is_available = self._connect_qbittorrent()

    def _connect_qbittorrent(self) -> bool:
        try:
            self.qb_client = qBittorrentClient(host=config.QBITTORRENT_HOST, username=config.QBITTORRENT_USERNAME,
                                               password=config.QBITTORRENT_PASSWORD)
            self.qb_client._session.timeout = 30
            self.qb_client.auth_log_in()
            self.qb_client.app_version()
            self.is_available = True
            return True
        except Exception:
            self.qb_client = None
            self.is_available = False
            return False

    def download_torrent(self, item: DownloadItem) -> bool:
        if not self.is_available or not self.qb_client:
            item.status = "failed"
            item.error_message = "qBittorrent not available"
            self.db.update_download(item, force=True)
            return False
        self.pause_event.wait()
        try:
            save_path = str(config.TORRENTSDIR)
            if item.url.startswith('magnet:'):
                result = self.qb_client.torrents_add(urls=item.url, save_path=save_path)
            else:
                response = requests.get(item.url, timeout=30)
                response.raise_for_status()
                result = self.qb_client.torrents_add(torrent_files=response.content, save_path=save_path)
            if result == "Ok.":
                item.status = "downloading"
                self.db.update_download(item, force=True)
                console.print(f"[blue]Torrent added: {item.title}[/blue]")
                return self._monitor_torrent(item)
            else:
                item.status = "failed"
                item.error_message = f"Failed to add torrent: {result}"
                self.db.update_download(item, force=True)
                return False
        except Exception as e:
            item.status = "failed"
            item.error_message = str(e)[:400]
            self.db.update_download(item, force=True)
            return False

    def _monitor_torrent(self, item: DownloadItem) -> bool:
        try:
            torrents = self.qb_client.torrents_info()
            target_torrent = None
            for torrent in torrents:
                if item.url.startswith('magnet:') and torrent.magnet_uri == item.url:
                    target_torrent = torrent
                    break
                elif torrent.name in item.title or item.title in torrent.name:
                    target_torrent = torrent
                    break
            if not target_torrent:
                item.status = "failed"
                item.error_message = "Torrent not found in client"
                self.db.update_download(item, force=True)
                return False
            item.title = target_torrent.name
            item.file_size = target_torrent.size
            while not self.shutdown_event.is_set():
                try:
                    self.pause_event.wait()
                    torrent = self.qb_client.torrents_info(torrent_hashes=target_torrent.hash)[0]
                    item.progress = torrent.progress * 100
                    item.downloaded_bytes = torrent.downloaded
                    item.upload_bytes = torrent.uploaded
                    item.download_speed = format_speed(torrent.dlspeed) if torrent.dlspeed > 0 else None
                    item.upload_speed = format_speed(torrent.upspeed) if torrent.upspeed > 0 else None
                    item.seeds = torrent.num_seeds
                    item.peers = torrent.num_leechs
                    item.ratio = torrent.ratio
                    if torrent.eta != 8640000:
                        item.eta = format_time(torrent.eta)
                    if item.id:
                        size_display = f" | {format_file_size(item.downloaded_bytes)}/{format_file_size(item.file_size)}"
                        progress_msg = (
                            f"Download {item.id} (Torrent): {item.title[:35]}... | "
                            f"{item.progress_percentage}%{size_display} | "
                            f"D:{item.download_speed or '0 B/s'} U:{item.upload_speed or '0 B/s'} | "
                            f"S:{item.seeds} P:{item.peers} | ETA: {item.eta or 'Unknown'}"
                        )
                        progress_display.update_progress(item.id, progress_msg)
                    self.db.update_download(item)
                    if torrent.state in ['completedDL', 'uploading', 'stalledUP']:
                        item.status = "completed"
                        item.progress = 100.0
                        item.completed_at = time.strftime('%Y-%m-%d %H:%M:%S')
                        self.db.update_download(item, force=True)
                        if item.id:
                            progress_display.remove_download(item.id)
                        console.print(f"[green]* Torrent completed: {item.title}[/green]")
                        return True
                    if torrent.state in ['error', 'missingFiles']:
                        item.status = "failed"
                        item.error_message = f"Torrent error: {torrent.state}"
                        self.db.update_download(item, force=True)
                        if item.id:
                            progress_display.remove_download(item.id)
                        return False
                    time.sleep(2)
                except Exception as e:
                    self.logger.error(f"Error monitoring torrent: {e}")
                    time.sleep(5)
                    continue
            return False
        except Exception as e:
            item.status = "failed"
            item.error_message = str(e)[:400]
            self.db.update_download(item, force=True)
            if item.id:
                progress_display.remove_download(item.id)
            return False


class DownloadManager:
    def __init__(self):
        self.db = DatabaseManager()
        self.logger = Logger(config.LOGFILE)
        aria2c_manager.set_logger(self.logger)
        self.shutdown_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.video_downloader = None
        self.file_downloader = None
        self.torrent_downloader = None
        self.aria2c_downloader = None
        self.executor = ThreadPoolExecutor(max_workers=config.CONCURRENTDOWNLOADS)
        self.running = False
        self.active_downloads = {}
        self.monitor_thread = None
        self.state_file = config.STATE_FILE
        self.load_state()
        self._setup_hotkeys()
        network_monitor.start()
        self._start_aria2c()

    def _start_aria2c(self):
        if not aria2c_manager.is_running:
            aria2c_manager.start()

    def _get_video_downloader(self):
        if self.video_downloader is None:
            self.video_downloader = VideoDownloader(self.db, self.shutdown_event, self.pause_event)
        return self.video_downloader

    def _get_file_downloader(self):
        if self.file_downloader is None:
            self.file_downloader = FileDownloader(self.db, self.shutdown_event, self.pause_event)
        return self.file_downloader

    def _get_torrent_downloader(self):
        if self.torrent_downloader is None:
            self.torrent_downloader = TorrentDownloader(self.db, self.shutdown_event, self.pause_event)
        return self.torrent_downloader

    def _get_aria2c_downloader(self):
        if self.aria2c_downloader is None:
            self.aria2c_downloader = Aria2cDownloader(self.db, self.shutdown_event, self.pause_event)
        return self.aria2c_downloader

    def add_url(self, url: str, quality: str = "best", include_subtitles: bool = False, embed_chapters: bool = False) -> \
    Optional[int]:
        if not validate_url(url):
            console.print(f"[red]X Invalid URL: {url}[/red]")
            return None
        try:
            download_type = detect_url_type(url)
            item = DownloadItem(url=url, title="Pending...", status="pending", download_type=download_type,
                                quality=quality,
                                include_subtitles=include_subtitles, embed_chapters=embed_chapters)
            item_id = self.db.add_download(item)
            if item_id:
                item.id = item_id
                console.print(f"[green]* Added {download_type} download: {url[:60]}...[/green]")
                return item_id
            else:
                console.print(f"[yellow]! URL already exists in database[/yellow]")
                return None
        except Exception as e:
            console.print(f"[red]X Failed to add URL: {e}[/red]")
            return None

    def start_downloads(self) -> bool:
        if self.running:
            console.print("[yellow]Downloads already running[/yellow]")
            return False

        pending = self.db.get_downloads_by_status("pending")
        if not pending:
            console.print("[blue]No pending downloads[/blue]")
            return False

        if not test_connection():
            console.print("[red]X Network connectivity check failed[/red]")
            return False

        self.running = True
        self.shutdown_event.clear()

        parallel_count = min(len(pending), config.CONCURRENTDOWNLOADS)
        avg_speed_per_video = 2.5
        estimated_total = parallel_count * avg_speed_per_video

        console.print(f"\n[green]Starting {len(pending)} downloads...[/green]")
        console.print(f"[dim]Concurrent downloads: {parallel_count}[/dim]")
        console.print(
            f"[dim]Estimated throughput: ~{estimated_total:.1f} MB/s ({parallel_count} x ~{avg_speed_per_video} MB/s)[/dim]")
        console.print()

        speeds = network_monitor.get_speeds()
        console.print(f"[dim]Network: DOWN {speeds['download']} | UP {speeds['upload']}[/dim]\n")

        futures = []
        for item in pending:
            future = self.executor.submit(self._process_download, item)
            futures.append(future)
            self.active_downloads[item.id] = future

        def monitor_downloads():
            completed = 0
            failed = 0
            try:
                for future in as_completed(futures):
                    if self.shutdown_event.is_set():
                        break
                    try:
                        success = future.result()
                        if success:
                            completed += 1
                        else:
                            failed += 1
                    except Exception as e:
                        self.logger.error(f"Download thread error: {e}")
                        failed += 1
                    for item_id, f in list(self.active_downloads.items()):
                        if f == future:
                            self.active_downloads.pop(item_id, None)
                            break
            finally:
                self.running = False
                console.print(f"\n[green]Download session complete - Success: {completed}, Failed: {failed}[/green]")

        self.monitor_thread = threading.Thread(target=monitor_downloads, daemon=True)
        self.monitor_thread.start()
        return True

    def _process_download(self, item: DownloadItem) -> bool:
        try:
            if self.shutdown_event.is_set():
                return False
            if item.download_type == "torrent":
                torrent_downloader = self._get_torrent_downloader()
                if not torrent_downloader.is_available:
                    item.status = "failed"
                    item.error_message = "qBittorrent not available"
                    self.db.update_download(item, force=True)
                    console.print(f"[red]X Skipping torrent - qBittorrent not available[/red]")
                    return False
            item.status = "downloading"
            self.db.update_download(item, force=True)
            self.pause_event.wait()
            if item.download_type in ["file", "video"] and aria2c_manager.is_running:
                aria2c_downloader = self._get_aria2c_downloader()
                if item.download_type == "video":
                    return self._get_video_downloader().download(item, item.quality or "best")
                else:
                    return aria2c_downloader.download_file(item)
            else:
                if item.download_type == "video":
                    return self._get_video_downloader().download(item, item.quality or "best")
                elif item.download_type == "file":
                    return self._get_file_downloader().download_file(item)
                elif item.download_type == "torrent":
                    return self._get_torrent_downloader().download_torrent(item)
                else:
                    item.status = "failed"
                    item.error_message = f"Unsupported download type: {item.download_type}"
                    self.db.update_download(item, force=True)
                    return False
        except Exception as e:
            self.logger.error(f"Download processing error: {e}")
            item.status = "failed"
            item.error_message = str(e)[:400]
            self.db.update_download(item, force=True)
            return False

    def stop_downloads(self):
        console.print("[yellow]Stopping downloads...[/yellow]")
        self.shutdown_event.set()
        for item_id, future in list(self.active_downloads.items()):
            try:
                future.cancel()
            except Exception:
                pass
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
        self.active_downloads.clear()
        self.running = False

    def get_download_stats(self) -> Dict[str, int]:
        return self.db.get_download_stats()

    def get_downloads_by_status(self, status: str, limit: int = 100) -> List[DownloadItem]:
        return self.db.get_downloads_by_status(status, limit)

    def get_all_downloads(self, limit: int = 100) -> List[DownloadItem]:
        return self.db.get_all_downloads(limit)

    def remove_downloads(self, download_ids: List[int]) -> int:
        for download_id in download_ids:
            if download_id in self.active_downloads:
                try:
                    self.active_downloads[download_id].cancel()
                    del self.active_downloads[download_id]
                except Exception:
                    pass
        return self.db.remove_downloads(download_ids)

    def clear_completed_downloads(self) -> int:
        return self.db.clear_completed_downloads()

    def clear_failed_downloads(self) -> int:
        return self.db.clear_failed_downloads()

    def retry_failed_downloads(self) -> int:
        failed = self.db.get_downloads_by_status("failed")
        retry_count = 0
        for item in failed:
            item.status = "pending"
            item.error_message = None
            item.attempts = 0
            if self.db.update_download(item, force=True):
                retry_count += 1
        console.print(f"[green]Reset {retry_count} failed downloads to pending[/green]")
        return retry_count

    def pause_downloads(self):
        if not self.pause_event.is_set():
            console.print("[yellow]Downloads are already paused.[/yellow]")
            return
        self.pause_event.clear()
        console.print("[yellow]Pausing downloads... (waiting for current operations to pause)[/yellow]")

        # Give downloads time to pause naturally
        time.sleep(0.5)

        try:
            downloading_items = self.db.get_downloads_by_status("downloading")
            for item in downloading_items:
                item.status = "paused"
                self.db.update_download(item, force=True)
            console.print("[yellow]Downloads paused. Press Ctrl+Shift+R to resume.[/yellow]")
        except Exception as e:
            self.logger.error(f"Failed to pause downloads: {e}")
        self.save_state(
            {'paused': True, 'active_downloads': list(self.active_downloads.keys()), 'timestamp': time.time()})

    def resume_downloads(self):
        if self.pause_event.is_set():
            console.print("[yellow]Downloads are already running.[/yellow]")
            return

        self.pause_event.set()
        console.print("[green]Resuming downloads...[/green]")

        try:
            paused_downloads = self.db.get_downloads_by_status("paused")
            if paused_downloads:
                for item in paused_downloads:
                    item.status = "downloading"
                    self.db.update_download(item, force=True)
                console.print(f"[green]Resumed {len(paused_downloads)} paused download(s)[/green]")
            else:
                console.print("[dim]No paused downloads to resume[/dim]")
        except Exception as e:
            self.logger.error(f"Failed to resume downloads: {e}")

        self.save_state(
            {'paused': False, 'active_downloads': list(self.active_downloads.keys()), 'timestamp': time.time()})

    def _setup_hotkeys(self):
        try:
            keyboard.add_hotkey(config.PAUSE_HOTKEY, self.pause_downloads)
            keyboard.add_hotkey(config.RESUME_HOTKEY, self.resume_downloads)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not setup hotkeys: {e}[/yellow]")

    def save_state(self, state_data: dict):
        config.save_state(state_data)

    def load_state(self):
        state = config.load_state()
        if state.get('paused', False):
            self.pause_event.clear()
            console.print("[yellow]Downloads were paused. Press Ctrl+Shift+R to resume.[/yellow]")

    def cleanup(self):
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        network_monitor.stop()
        aria2c_manager.stop()


class CLI:
    def __init__(self):
        self.manager = DownloadManager()
        self.logger = Logger(config.LOGFILE)
        self.running = True
        self._system_status = None
        signal.signal(signal.SIGINT, self._signal_handler)
        self._show_banner()

    def _signal_handler(self, signum, frame):
        console.print("\n[yellow]Shutting down gracefully...[/yellow]")
        self.manager.stop_downloads()
        self.manager.cleanup()
        self.running = False
        sys.exit(0)

    def _show_banner(self):
        console.print("\n" + "=" * 70)
        console.print("Advanced Download Manager v2.2 - Speed Optimized".center(70))
        console.print("aria2c Auto-Launch | Real Speed Tracking".center(70))
        console.print("=" * 70 + "\n")

        console.print("[dim]Initializing system components...[/dim]")
        status_table = Table(show_header=False, box=box.SIMPLE)
        status_table.add_column("Feature", style="cyan")
        status_table.add_column("Status", style="bold")
        status_table.add_row("FFmpeg (Video Processing)", "[yellow]Checking...[/yellow]")
        status_table.add_row("aria2c (Max Speed Downloads)", "[yellow]Checking...[/yellow]")
        status_table.add_row("qBittorrent (Torrents)", "[yellow]Checking...[/yellow]")
        status_table.add_row("Network Monitor", "[yellow]Starting...[/yellow]")
        console.print(status_table)
        console.print()
        self._start_background_checks()

    def _start_background_checks(self):
        def check_systems():
            try:
                has_ffmpeg, ffmpeg_cmd = check_ffmpeg()
                ffmpeg_status = "[green]* Available[/green]" if has_ffmpeg else "[red]X Not Found[/red]"
                if has_ffmpeg and ffmpeg_cmd:
                    ffmpeg_status += f" [dim]({ffmpeg_cmd})[/dim]"
                has_aria2c = aria2c_manager.is_running
                aria2c_status = f"[green]* Running on port {config.ARIA2C_RPC_PORT}[/green]" if has_aria2c else "[red]X Not Available[/red]"
                has_qbittorrent = check_qbittorrent()
                qb_status = "[green]* Connected[/green]" if has_qbittorrent else "[red]X Not Available[/red]"
                speeds = network_monitor.get_speeds()
                net_status = f"[green]* Active (DOWN {speeds['download']} | UP {speeds['upload']})[/green]"
                self._system_status = {
                    'ffmpeg': ffmpeg_status, 'aria2c': aria2c_status, 'qbittorrent': qb_status,
                    'network': net_status, 'has_aria2c': has_aria2c, 'has_qbittorrent': has_qbittorrent
                }
            except Exception as e:
                self.logger.error(f"Background system check failed: {e}")

        threading.Thread(target=check_systems, daemon=True).start()

    def run(self):
        try:
            while self.running:
                self._show_main_menu()
                choice = console.input("\n[bold cyan]Choice:[/bold cyan] ").strip()
                if choice == '1':
                    self._add_urls_menu()
                elif choice == '2':
                    self._start_downloads()
                elif choice == '3':
                    self._view_downloads_menu()
                elif choice == '4':
                    self._manage_downloads_menu()
                elif choice == '5':
                    self._settings_menu()
                elif choice == '6':
                    self._exit()
                else:
                    console.print("[red]Invalid choice[/red]")
                console.input("\n[dim]Press Enter to continue...[/dim]")
        except KeyboardInterrupt:
            self._signal_handler(signal.SIGINT, None)

    def _show_main_menu(self):
        console.clear()
        stats = self.manager.get_download_stats()
        stats_text = f"Total: {stats.get('total', 0)} | Pending: {stats.get('pending', 0)} | Downloading: {stats.get('downloading', 0)} | Completed: {stats.get('completed', 0)} | Failed: {stats.get('failed', 0)}"

        console.print("=" * 70)
        console.print("MAIN MENU".center(70))
        console.print("=" * 70)
        console.print()
        console.print(f"[dim]{stats_text}[/dim]")
        console.print()

        if self._system_status:
            speeds = network_monitor.get_speeds()
            console.print("[dim]System Status:[/dim]")
            console.print(f"  FFmpeg: {self._system_status['ffmpeg']}")
            console.print(f"  aria2c: {self._system_status['aria2c']}")
            console.print(f"  qBittorrent: {self._system_status['qbittorrent']}")
            console.print(f"  Network: [green]DOWN {speeds['download']} | UP {speeds['upload']}[/green]")
            console.print()

        console.print("[bold]1.[/bold] Add URLs for Download")
        console.print("[bold]2.[/bold] Start Downloads")
        console.print("[bold]3.[/bold] View Downloads")
        console.print("[bold]4.[/bold] Manage Downloads")
        console.print("[bold]5.[/bold] Settings")
        console.print("[bold]6.[/bold] Exit")
        console.print()
        console.print("=" * 70)
        console.print()
        console.print("[dim]Hotkeys: Ctrl+Shift+P (Pause) | Ctrl+Shift+R (Resume)[/dim]")

    def _add_urls_menu(self):
        console.clear()
        console.print("[bold cyan]Add URLs for Download[/bold cyan]\n")
        url = console.input("[bold]Enter URL (file/video/torrent/magnet):[/bold] ").strip()
        if not url:
            return
        url_type = detect_url_type(url)
        console.print(f"[dim]Detected type: {url_type}[/dim]\n")
        if url_type == "torrent" and not check_qbittorrent():
            console.print("[red]X Cannot add torrent: qBittorrent is not available[/red]")
            console.print("[yellow]Please set up qBittorrent first using Settings[/yellow]")
            return
        quality = "best"
        include_subtitles = False
        embed_chapters = False
        if url_type == "video":
            console.print("[bold]Select Quality:[/bold]")
            for i, (name, _) in enumerate(config.QUALITY_OPTIONS, 1):
                console.print(f"[bold]{i}.[/bold] {name}")
            choice = console.input("\n[bold]Quality choice (default: 7):[/bold] ").strip()
            if choice and choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(config.QUALITY_OPTIONS):
                    quality = config.QUALITY_OPTIONS[idx][0]
            subs = console.input("[bold]Include subtitles? (Y/n):[/bold] ").strip().lower()
            include_subtitles = subs not in ['n', 'no']
            chapters = console.input("[bold]Embed chapters? (Y/n):[/bold] ").strip().lower()
            embed_chapters = chapters not in ['n', 'no']
        item_id = self.manager.add_url(url, quality, include_subtitles, embed_chapters)
        if item_id:
            console.print(f"\n[green]* Successfully added download (ID: {item_id})[/green]")
        else:
            console.print("\n[red]X Failed to add download[/red]")

    def _start_downloads(self):
        console.clear()
        console.print("[bold cyan]Starting Downloads[/bold cyan]\n")
        if self.manager.running:
            console.print("[yellow]Downloads are already running[/yellow]")
            return
        success = self.manager.start_downloads()
        if success:
            console.print("[green]* Downloads started successfully[/green]")
            console.print(
                "[dim]Downloads are running in the background. Use 'View Downloads' to monitor progress.[/dim]")
        else:
            console.print("[red]X Failed to start downloads[/red]")

    def _view_downloads_menu(self):
        console.clear()
        console.print("[bold cyan]View Downloads[/bold cyan]\n")
        console.print("[bold]1.[/bold] All Downloads")
        console.print("[bold]2.[/bold] Pending Downloads")
        console.print("[bold]3.[/bold] Active Downloads")
        console.print("[bold]4.[/bold] Completed Downloads")
        console.print("[bold]5.[/bold] Failed Downloads")
        choice = console.input("\n[bold]Choice:[/bold] ").strip()
        downloads = {
            '1': self.manager.get_all_downloads(),
            '2': self.manager.get_downloads_by_status("pending"),
            '3': self.manager.get_downloads_by_status("downloading"),
            '4': self.manager.get_downloads_by_status("completed"),
            '5': self.manager.get_downloads_by_status("failed")
        }.get(choice)
        if downloads is None:
            console.print("[red]Invalid choice[/red]")
            return
        self._display_downloads_table(downloads)

    def _display_downloads_table(self, downloads: List[DownloadItem]):
        if not downloads:
            console.print("\n[yellow]No downloads found[/yellow]")
            return
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("ID", width=4)
        table.add_column("Type", width=8)
        table.add_column("Title", width=40)
        table.add_column("Status", width=12)
        table.add_column("Progress", width=10)
        table.add_column("Speed", width=12)
        table.add_column("Size", width=10)
        for item in downloads:
            status_map = {
                "completed": "[green]completed[/green]",
                "downloading": "[blue]downloading[/blue]",
                "failed": "[red]failed[/red]",
                "pending": "[yellow]pending[/yellow]"
            }
            status = status_map.get(item.status, item.status)
            progress = f"{item.progress_percentage}%"
            if item.status == "downloading":
                progress = f"[blue]{progress}[/blue]"
            elif item.status == "completed":
                progress = f"[green]{progress}[/green]"
            size = format_file_size(item.file_size) if item.file_size else "Unknown"
            table.add_row(
                str(item.id or ""), item.download_type,
                item.title[:40] + "..." if len(item.title) > 40 else item.title,
                status, progress, item.download_speed or "", size
            )
        console.print(table)
        speeds = network_monitor.get_speeds()
        console.print(f"\n[dim]Real Network Speed: DOWN {speeds['download']} | UP {speeds['upload']}[/dim]")

    def _manage_downloads_menu(self):
        console.clear()
        console.print("[bold cyan]Manage Downloads[/bold cyan]\n")
        console.print("[bold]1.[/bold] Pause All Downloads")
        console.print("[bold]2.[/bold] Resume All Downloads")
        console.print("[bold]3.[/bold] Check Pause Status")
        console.print("[bold]4.[/bold] Stop All Downloads")
        console.print("[bold]5.[/bold] Retry Failed Downloads")
        console.print("[bold]6.[/bold] Clear Completed Downloads")
        console.print("[bold]7.[/bold] Clear Failed Downloads")
        console.print("[bold]8.[/bold] Remove Downloads by ID")
        console.print("[bold]9.[/bold] Download Statistics")
        choice = console.input("\n[bold]Choice:[/bold] ").strip()
        if choice == '1':
            self.manager.pause_downloads()
        elif choice == '2':
            self.manager.resume_downloads()
        elif choice == '3':
            if self.manager.pause_event.is_set():
                console.print("[green]* Downloads are running (not paused)[/green]")
            else:
                console.print("[yellow]! Downloads are paused[/yellow]")
        elif choice == '4':
            self.manager.stop_downloads()
            console.print("[yellow]* All downloads stopped[/yellow]")
        elif choice == '5':
            count = self.manager.retry_failed_downloads()
            console.print(f"[green]* Reset {count} failed downloads to pending[/green]")
        elif choice == '6':
            count = self.manager.clear_completed_downloads()
            console.print(f"[green]* Cleared {count} completed downloads[/green]")
        elif choice == '7':
            count = self.manager.clear_failed_downloads()
            console.print(f"[green]* Cleared {count} failed downloads[/green]")
        elif choice == '8':
            console.print("\n[bold cyan]Available Downloads:[/bold cyan]")
            all_downloads = self.manager.get_all_downloads(50)
            if all_downloads:
                table = Table(show_header=True, header_style="bold cyan")
                table.add_column("ID", width=4)
                table.add_column("Type", width=8)
                table.add_column("Title", width=40)
                table.add_column("Status", width=12)
                for item in all_downloads:
                    status_map = {
                        "completed": "[green]completed[/green]",
                        "downloading": "[blue]downloading[/blue]",
                        "failed": "[red]failed[/red]"
                    }
                    status = status_map.get(item.status, item.status)
                    table.add_row(
                        str(item.id or ""), item.download_type,
                        item.title[:40] + "..." if len(item.title) > 40 else item.title, status
                    )
                console.print(table)
                console.print()
            ids_input = console.input("[bold]Enter download IDs to remove (comma-separated):[/bold] ").strip()
            try:
                ids = [int(x.strip()) for x in ids_input.split(',') if x.strip()]
                count = self.manager.remove_downloads(ids)
                console.print(f"[green]* Removed {count} downloads[/green]")
            except ValueError:
                console.print("[red]X Invalid ID format[/red]")
        elif choice == '9':
            self._show_statistics()
        else:
            console.print("[red]Invalid choice[/red]")

    def _show_statistics(self):
        stats = self.manager.get_download_stats()
        stats_table = Table(show_header=True, header_style="bold cyan")
        stats_table.add_column("Status", style="bold")
        stats_table.add_column("Count", justify="right")
        for status, count in stats.items():
            if status == "total":
                stats_table.add_row("Total", str(count), style="bold")
            else:
                stats_table.add_row(status.title(), str(count))
        console.print("\n[bold cyan]Download Statistics[/bold cyan]")
        console.print(stats_table)

    def _settings_menu(self):
        console.clear()
        console.print("[bold cyan]Settings[/bold cyan]\n")
        console.print("[bold]1.[/bold] Change Download Directory")
        console.print("[bold]2.[/bold] Change Concurrent Downloads")
        console.print("[bold]3.[/bold] Check Dependencies Status")
        console.print("[bold]4.[/bold] View Current Settings")
        choice = console.input("\n[bold]Choice:[/bold] ").strip()

        if choice == '1':
            new_path = console.input("[bold]Enter new download directory path:[/bold] ").strip()
            if new_path:
                if config.set_download_directory(new_path):
                    console.print(f"[green]* Download directory changed to: {new_path}[/green]")
                else:
                    console.print("[red]X Failed to change directory[/red]")
        elif choice == '2':
            current = config.CONCURRENTDOWNLOADS
            console.print(f"\n[dim]Current setting: {current}[/dim]")
            console.print("[dim]Recommended: 8-16 for multiplied throughput[/dim]")
            console.print("[dim]Maximum: 32 (higher may cause system issues)[/dim]")
            new_val = console.input(f"[bold]New value (1-32, default was 10):[/bold] ").strip()
            try:
                val = int(new_val)
                if 1 <= val <= 32:
                    config.CONCURRENTDOWNLOADS = val
                    config.save_settings()
                    console.print(f"\n[green]* Concurrent downloads set to {val}[/green]")
                    console.print(f"[dim]Expected throughput: {val}x parallel downloads[/dim]")
                    if val >= 8:
                        console.print(f"[dim]If each download: 1-3 MB/s, total: ~{val}-{val * 3} MB/s[/dim]")
                else:
                    console.print("[red]X Value must be between 1 and 32[/red]")
            except ValueError:
                console.print("[red]X Invalid number[/red]")
        elif choice == '3':
            self._check_all_dependencies()
        elif choice == '4':
            self._show_current_settings()
        else:
            console.print("[red]Invalid choice[/red]")

    def _check_all_dependencies(self):
        console.clear()
        console.print("[bold cyan]Dependencies Status Check[/bold cyan]\n")
        deps_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
        deps_table.add_column("Dependency", style="bold", width=25)
        deps_table.add_column("Status", width=20)
        deps_table.add_column("Details", width=50)
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        if sys.version_info >= (3, 7):
            deps_table.add_row("Python", "[green]* Installed[/green]", f"Version {python_version}")
        else:
            deps_table.add_row("Python", "[red]X Too Old[/red]", f"Version {python_version} (need 3.7+)")
        packages = [
            ('yt-dlp', 'yt_dlp'), ('requests', 'requests'), ('rich', 'rich'), ('psutil', 'psutil'),
            ('keyboard', 'keyboard'), ('qbittorrent-api', 'qbittorrentapi'), ('click', 'click'),
        ]
        for package_name, import_name in packages:
            try:
                module = __import__(import_name)
                try:
                    import importlib.metadata
                    version = importlib.metadata.version(package_name)
                except Exception:
                    version = getattr(module, '__version__', 'Unknown')
                deps_table.add_row(package_name, "[green]* Installed[/green]", f"Version {version}")
            except ImportError:
                deps_table.add_row(package_name, "[red]X Missing[/red]", f"Install: pip install {package_name}")
        has_ffmpeg, ffmpeg_path = check_ffmpeg()
        if has_ffmpeg:
            try:
                result = subprocess.run([ffmpeg_path, '-version'], capture_output=True, text=True, timeout=3)
                version_line = result.stdout.split('\n')[0] if result.stdout else 'Unknown'
                deps_table.add_row("FFmpeg", "[green]* Installed[/green]", version_line[:50])
            except:
                deps_table.add_row("FFmpeg", "[green]* Installed[/green]", ffmpeg_path[:50])
        else:
            deps_table.add_row("FFmpeg", "[red]X Not Found[/red]", "Required for video processing")
        aria2c_path = aria2c_manager.find_aria2c()
        if aria2c_path:
            try:
                result = subprocess.run([aria2c_path, '--version'], capture_output=True, text=True, timeout=3)
                version_line = result.stdout.split('\n')[0] if result.stdout else 'Unknown'
                status = "[green]* Running[/green]" if aria2c_manager.is_running else "[yellow]! Found but not running[/yellow]"
                deps_table.add_row("aria2c", status, version_line[:50])
            except:
                deps_table.add_row("aria2c", "[yellow]! Found[/yellow]", aria2c_path[:50])
        else:
            deps_table.add_row("aria2c", "[red]X Not Found[/red]", "Optional: For maximum download speed")
        qb_available = check_qbittorrent()
        if qb_available:
            deps_table.add_row("qBittorrent", "[green]* Connected[/green]", f"Host: {config.QBITTORRENT_HOST}")
        else:
            deps_table.add_row("qBittorrent", "[red]X Not Available[/red]", "Optional: For torrent downloads")
        has_network = test_connection()
        if has_network:
            speeds = network_monitor.get_speeds()
            deps_table.add_row("Network", "[green]* Connected[/green]",
                               f"DOWN {speeds['download']} | UP {speeds['upload']}")
        else:
            deps_table.add_row("Network", "[red]X No Connection[/red]", "Check internet connection")
        console.print(deps_table)
        console.print()
        console.print("[bold cyan]Installation Instructions:[/bold cyan]")
        console.print()
        console.print("[bold]Python Packages:[/bold]")
        console.print("  pip install yt-dlp requests rich psutil keyboard qbittorrent-api click")
        console.print()
        console.print("[bold]FFmpeg:[/bold]")
        console.print("  Windows: Download from https://github.com/BtbN/FFmpeg-Builds/releases")
        console.print("  Linux: sudo apt install ffmpeg")
        console.print("  macOS: brew install ffmpeg")
        console.print()
        console.print("[bold]aria2c (Optional - for maximum speed):[/bold]")
        console.print("  Download from: https://github.com/aria2/aria2/releases")
        console.print()
        console.print("[bold]qBittorrent (Optional - for torrents):[/bold]")
        console.print("  Download from: https://www.qbittorrent.org/download.php")
        console.print("  Enable Web UI in settings on port 8080")

    def _show_current_settings(self):
        settings_table = Table(show_header=True, header_style="bold cyan")
        settings_table.add_column("Setting", style="bold")
        settings_table.add_column("Value")
        settings_table.add_row("Download Directory", str(config.BASEDIR))
        settings_table.add_row("Concurrent Downloads", str(config.CONCURRENTDOWNLOADS))
        settings_table.add_row("Max Connections", str(config.MAXCONNECTIONS))
        settings_table.add_row("aria2c Status", "Running" if aria2c_manager.is_running else "Not Running")
        settings_table.add_row("aria2c Port", str(config.ARIA2C_RPC_PORT))
        settings_table.add_row("qBittorrent Host", config.QBITTORRENT_HOST)
        console.print(settings_table)

    def _exit(self):
        console.print("[yellow]Shutting down...[/yellow]")
        self.manager.stop_downloads()
        self.manager.cleanup()
        self.running = False
        console.print("[green]Goodbye![/green]")
        sys.exit(0)


def main():
    try:
        config.load_settings()
        cli = CLI()
        cli.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        aria2c_manager.stop()
        network_monitor.stop()
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        aria2c_manager.stop()
        network_monitor.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()