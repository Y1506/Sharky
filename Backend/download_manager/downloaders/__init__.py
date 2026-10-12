from .base import BaseDownloader
from .aria2 import Aria2cDownloader, aria2c_manager
from .video import VideoDownloader
from .file import FileDownloader
from .torrent import TorrentDownloader

__all__ = [
    "BaseDownloader",
    "Aria2cDownloader",
    "aria2c_manager",
    "VideoDownloader",
    "FileDownloader",
    "TorrentDownloader",
]
