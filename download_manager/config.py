import json
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, Optional, Any
from rich.console import Console

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
    COOKIE_MAX_AGE: int = 86400  # 24 hours in seconds
    COOKIE_BROWSER_ORDER: List[str] = field(default_factory=lambda: ['zen', 'brave'])
    COOKIE_MANUAL_PATH: Optional[str] = None  # Manual cookie file path
    COOKIE_BROWSER_PATH: Optional[str] = None  # Manual browser profile path
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
                'cookie_max_age': self.COOKIE_MAX_AGE,
                'cookie_browser_order': self.COOKIE_BROWSER_ORDER,
                'cookie_manual_path': self.COOKIE_MANUAL_PATH,
                'cookie_browser_path': self.COOKIE_BROWSER_PATH,
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
