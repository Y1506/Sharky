import os
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, Optional, Any
from rich.console import Console

console = Console()

def get_default_basedir() -> Path:
    env_dir = os.environ.get('DOWNLOAD_DIR')
    if env_dir:
        return Path(env_dir).resolve()
    # Default to downloads folder in workspace or current directory
    return (Path.cwd() / 'downloads').resolve()

@dataclass
class Config:
    BASEDIR: Path = field(default_factory=get_default_basedir)
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
    RETRYDELAY: float = 0.2
    CHUNKSIZE: int = 4194304
    MAXCONNECTIONS: int = 16
    BUFFER_SIZE: int = 33554432
    DOWNLOAD_SPEED_LIMIT: int = 0  # In bytes/second, 0 = unlimited
    QBITTORRENT_HOST: str = field(default_factory=lambda: os.environ.get('QBITTORRENT_HOST', 'http://localhost:8080'))
    QBITTORRENT_USERNAME: str = field(default_factory=lambda: os.environ.get('QBITTORRENT_USERNAME', 'admin'))
    QBITTORRENT_PASSWORD: str = field(default_factory=lambda: os.environ.get('QBITTORRENT_PASSWORD', 'adminadmin'))
    ARIA2C_RPC_PORT: int = 6800
    ARIA2C_SECRET: str = field(default_factory=lambda: os.environ.get('ARIA2C_SECRET', 'aria2secret'))
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
    COOKIE_MAX_AGE: int = 86400  # 24 hours in seconds
    COOKIE_BROWSER_ORDER: List[str] = field(default_factory=lambda: ['zen', 'brave'])
    COOKIE_MANUAL_PATH: Optional[str] = None  # Manual cookie file path
    COOKIE_BROWSER_PATH: Optional[str] = None  # Manual browser profile path
    qualityoptions: Optional[List[Tuple[str, str]]] = None

    # Transmission / Speed Limits
    UPLOAD_SPEED_LIMIT: int = 0  # In bytes/second, 0 = unlimited

    # Startup & General
    AUTO_RESUME_UNFINISHED: bool = False

    # BitTorrent Configuration
    BT_SAVE_MAGNET_AS_TORRENT: bool = True
    BT_AUTO_DOWNLOAD_CONTENT: bool = True
    BT_FORCE_ENCRYPTION: bool = False
    BT_KEEP_SEEDING: bool = False
    BT_SEED_RATIO: float = 1.0
    BT_SEED_TIME: int = 60  # minutes
    BT_LISTEN_PORT: int = 21301
    DHT_LISTEN_PORT: int = 26701
    ENABLE_UPNP: bool = True

    # Network & Proxy
    PROXY_ENABLED: bool = False
    PROXY_URL: str = ""

    # Trackers
    BT_TRACKERS: str = ""
    BT_TRACKER_SOURCES: List[str] = field(default_factory=lambda: [
        "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_best_ip.txt",
        "https://raw.githubusercontent.com/XIU2/TrackersListCollection/master/best.txt"
    ])
    BT_AUTO_UPDATE_TRACKERS: bool = True
    BT_TRACKERS_LAST_UPDATED: str = ""

    # User-Agent
    USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    # Developer & Engine Paths
    ARIA2_CONF_PATH: Optional[str] = None
    SESSION_PATH: Optional[str] = None
    LOG_PATH: Optional[str] = None
    LOG_LEVEL: str = "warn"

    def __post_init__(self):
        self.VIDEODIR = self.BASEDIR / 'videos'
        self.AUDIODIR = self.BASEDIR / 'audio'
        self.FILESDIR = self.BASEDIR / 'files'
        self.TORRENTSDIR = self.BASEDIR / 'torrents'
        self.DATABASEFILE = self.BASEDIR / 'downloads.db'
        self.LOGFILE = self.BASEDIR / 'download_manager.log'
        self.SETTINGSFILE = self.BASEDIR / 'settings.json'
        self.STATE_FILE = self.BASEDIR / 'download_state.json'
        if not self.SESSION_PATH:
            self.SESSION_PATH = str(self.BASEDIR / 'download.session')
        if not self.LOG_PATH:
            self.LOG_PATH = str(self.LOGFILE)

        for directory in [self.BASEDIR, self.VIDEODIR, self.AUDIODIR, self.FILESDIR, self.TORRENTSDIR]:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                console.print(f'[red]Warning: Could not create directory {directory}: {e}[/red]')

    @property
    def CONFIG_FILE(self) -> Path:
        return self.SETTINGSFILE

    @CONFIG_FILE.setter
    def CONFIG_FILE(self, value: Path):
        self.SETTINGSFILE = value

    @property
    def DBFILE(self) -> Path:
        return self.DATABASEFILE

    @DBFILE.setter
    def DBFILE(self, value: Path):
        self.DATABASEFILE = value

    @property
    def ARIA2C_RPC_SECRET(self) -> str:
        return self.ARIA2C_SECRET

    @ARIA2C_RPC_SECRET.setter
    def ARIA2C_RPC_SECRET(self, value: str):
        self.ARIA2C_SECRET = value

    def load_settings(self):
        try:
            settings_path = self.SETTINGSFILE if self.SETTINGSFILE.exists() else Path('settings.json')
            if settings_path.exists():
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)

                alias_map = {
                    'concurrent_downloads': 'CONCURRENTDOWNLOADS',
                    'concurrentdownloads': 'CONCURRENTDOWNLOADS',
                    'max_connections_per_server': 'ARIA2C_MAX_CONNECTIONS',
                    'continue_download': 'ARIA2C_CONTINUE',
                }

                for key, value in settings.items():
                    target_attr = alias_map.get(key, key.upper())
                    if key == 'basedir' or key == 'download_dir':
                        if not os.environ.get('DOWNLOAD_DIR'):
                            self.BASEDIR = Path(value).resolve()
                            self.__post_init__()
                    elif hasattr(self, target_attr):
                        setattr(self, target_attr, value)
        except Exception as e:
            console.print(f'[yellow]Warning: Failed to load settings: {e}[/yellow]')

    def save_settings(self):
        try:
            saved_basedir = str(self.BASEDIR)
            if os.environ.get('DOWNLOAD_DIR') and self.SETTINGSFILE.exists():
                try:
                    with open(self.SETTINGSFILE, 'r', encoding='utf-8') as f:
                        old_s = json.load(f)
                        if 'basedir' in old_s:
                            saved_basedir = old_s['basedir']
                        elif 'download_dir' in old_s:
                            saved_basedir = old_s['download_dir']
                except Exception:
                    pass

            settings = {
                'basedir': saved_basedir,
                'download_dir': saved_basedir,
                'concurrent_downloads': self.CONCURRENTDOWNLOADS,
                'download_speed_limit': self.DOWNLOAD_SPEED_LIMIT,
                'upload_speed_limit': self.UPLOAD_SPEED_LIMIT,
                'max_connections_per_server': self.ARIA2C_MAX_CONNECTIONS,
                'continue_download': self.ARIA2C_CONTINUE,
                'auto_resume_unfinished': self.AUTO_RESUME_UNFINISHED,
                'bt_save_magnet_as_torrent': self.BT_SAVE_MAGNET_AS_TORRENT,
                'bt_auto_download_content': self.BT_AUTO_DOWNLOAD_CONTENT,
                'bt_force_encryption': self.BT_FORCE_ENCRYPTION,
                'bt_keep_seeding': self.BT_KEEP_SEEDING,
                'bt_seed_ratio': self.BT_SEED_RATIO,
                'bt_seed_time': self.BT_SEED_TIME,
                'bt_listen_port': self.BT_LISTEN_PORT,
                'dht_listen_port': self.DHT_LISTEN_PORT,
                'enable_upnp': self.ENABLE_UPNP,
                'proxy_enabled': self.PROXY_ENABLED,
                'proxy_url': self.PROXY_URL,
                'bt_trackers': self.BT_TRACKERS,
                'bt_tracker_sources': self.BT_TRACKER_SOURCES,
                'bt_auto_update_trackers': self.BT_AUTO_UPDATE_TRACKERS,
                'bt_trackers_last_updated': self.BT_TRACKERS_LAST_UPDATED,
                'user_agent': self.USER_AGENT,
                'aria2_conf_path': self.ARIA2_CONF_PATH,
                'session_path': self.SESSION_PATH,
                'log_path': self.LOG_PATH,
                'log_level': self.LOG_LEVEL,
                'aria2c_rpc_port': self.ARIA2C_RPC_PORT,
                'aria2c_secret': self.ARIA2C_SECRET,
                'qbittorrent_host': self.QBITTORRENT_HOST,
                'qbittorrent_username': self.QBITTORRENT_USERNAME,
                'qbittorrent_password': self.QBITTORRENT_PASSWORD,
                'cookie_max_age': self.COOKIE_MAX_AGE,
                'cookie_browser_order': self.COOKIE_BROWSER_ORDER,
                'cookie_manual_path': self.COOKIE_MANUAL_PATH,
                'cookie_browser_path': self.COOKIE_BROWSER_PATH,
            }

            self.SETTINGSFILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.SETTINGSFILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            console.print(f'[yellow]Warning: Failed to save settings: {e}[/yellow]')

    def update_trackers_from_remote(self) -> int:
        """Fetch trackers from configured remote tracker sources and merge with BT_TRACKERS."""
        import requests
        import datetime
        trackers_set = set()
        if self.BT_TRACKERS:
            for t in self.BT_TRACKERS.splitlines():
                t = t.strip()
                if t:
                    trackers_set.add(t)

        for url in self.BT_TRACKER_SOURCES:
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    for line in resp.text.splitlines():
                        line = line.strip()
                        if line and not line.startswith('#'):
                            trackers_set.add(line)
            except Exception as e:
                console.print(f"[yellow]Failed to fetch trackers from {url}: {e}[/yellow]")

        self.BT_TRACKERS = "\n".join(sorted(trackers_set))
        self.BT_TRACKERS_LAST_UPDATED = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_settings()
        return len(trackers_set)

    def reset_session(self) -> bool:
        """Reset / truncate aria2 download session file."""
        try:
            p = Path(self.SESSION_PATH or (self.BASEDIR / 'download.session'))
            if p.exists():
                p.unlink()
            p.touch()
            return True
        except Exception as e:
            console.print(f"[yellow]Failed to reset session: {e}[/yellow]")
            return False

    def factory_reset(self):
        """Restore default centralized configuration values."""
        self.CONCURRENTDOWNLOADS = 5
        self.DOWNLOAD_SPEED_LIMIT = 0
        self.UPLOAD_SPEED_LIMIT = 0
        self.ARIA2C_MAX_CONNECTIONS = 16
        self.ARIA2C_CONTINUE = True
        self.AUTO_RESUME_UNFINISHED = False
        self.BT_SAVE_MAGNET_AS_TORRENT = True
        self.BT_AUTO_DOWNLOAD_CONTENT = True
        self.BT_FORCE_ENCRYPTION = False
        self.BT_KEEP_SEEDING = False
        self.BT_SEED_RATIO = 1.0
        self.BT_SEED_TIME = 60
        self.BT_LISTEN_PORT = 21301
        self.DHT_LISTEN_PORT = 26701
        self.ENABLE_UPNP = True
        self.PROXY_ENABLED = False
        self.PROXY_URL = ""
        self.BT_TRACKERS = ""
        self.BT_AUTO_UPDATE_TRACKERS = True
        self.BT_TRACKERS_LAST_UPDATED = ""
        self.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.ARIA2_CONF_PATH = None
        self.SESSION_PATH = str(self.BASEDIR / 'download.session')
        self.LOG_PATH = str(self.BASEDIR / 'download_manager.log')
        self.LOG_LEVEL = "warn"
        self.ARIA2C_RPC_PORT = 6800
        self.ARIA2C_SECRET = "aria2secret"
        self.save_settings()

    def save_state(self, state_data: dict):
        """Save application state safely using atomic JSON write."""
        try:
            self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.STATE_FILE.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=2)
            temp_path.replace(self.STATE_FILE)
        except Exception as e:
            console.print(f'[yellow]Warning: Failed to save state: {e}[/yellow]')

    def load_state(self) -> dict:
        """Load application state from JSON."""
        try:
            if self.STATE_FILE.exists():
                with open(self.STATE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            console.print(f'[yellow]Warning: Failed to load state: {e}[/yellow]')
        return {}

    @property
    def QUALITY_OPTIONS(self) -> List[Tuple[str, str]]:
        if self.qualityoptions is None:
            self.qualityoptions = [
                ('4K (2160p)', 'bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/best[height<=2160]'),
                ('1440p (2K)', 'bestvideo[height<=1440][ext=mp4]+bestaudio[ext=m4a]/best[height<=1440]'),
                ('1080p60 High Bitrate', 'bestvideo[height<=1080][fps>=50][tbr>=3000][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080][tbr>=3000][ext=mp4]+bestaudio[ext=m4a]'),
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

