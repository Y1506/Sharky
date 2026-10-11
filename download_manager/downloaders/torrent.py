import time
import threading
import requests
from rich.console import Console
from qbittorrentapi import Client as qBittorrentClient
from ..config import config
from ..models import DownloadItem
from ..database import DatabaseManager
from ..utils import format_speed, format_time, format_file_size
from ..ui.display import progress_display
from .base import BaseDownloader

console = Console()

class TorrentDownloader(BaseDownloader):
    def __init__(self, db_manager: DatabaseManager, shutdown_event: threading.Event, pause_event: threading.Event):
        super().__init__(db_manager, shutdown_event, pause_event)
        self.qb_client = None
        self.is_available = self._connect_qbittorrent()
        self.logger = None

    def _connect_qbittorrent(self) -> bool:
        try:
            self.qb_client = qBittorrentClient(
                host=config.QBITTORRENT_HOST,
                username=config.QBITTORRENT_USERNAME,
                password=config.QBITTORRENT_PASSWORD
            )
            self.qb_client._session.timeout = 15
            self.qb_client.auth_log_in()
            self.qb_client.app_version()
            self.is_available = True
            return True
        except Exception:
            self.qb_client = None
            self.is_available = False
            return False

    def download(self, item: DownloadItem, **kwargs) -> bool:
        return self.download_torrent(item)

    def download_torrent(self, item: DownloadItem) -> bool:
        if not self.is_available or not self.qb_client:
            # Try one reconnect attempt in case qBittorrent came online
            if not self._connect_qbittorrent():
                item.status = "failed"
                item.error_message = "qBittorrent not available"
                self.db.update_download(item, force=True)
                return False

        if not self.wait_if_paused():
            return False

        try:
            save_path = str(config.TORRENTSDIR)
            config.TORRENTSDIR.mkdir(parents=True, exist_ok=True)

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
                if not self.wait_if_paused():
                    return False

                try:
                    torrent_list = self.qb_client.torrents_info(torrent_hashes=target_torrent.hash)
                    if not torrent_list:
                        break
                    torrent = torrent_list[0]

                    item.progress = torrent.progress * 100
                    item.downloaded_bytes = torrent.downloaded
                    item.upload_bytes = torrent.uploaded
                    item.download_speed = format_speed(torrent.dlspeed) if torrent.dlspeed > 0 else "0 B/s"
                    item.upload_speed = format_speed(torrent.upspeed) if torrent.upspeed > 0 else "0 B/s"
                    item.seeds = torrent.num_seeds
                    item.peers = torrent.num_leechs
                    item.ratio = torrent.ratio
                    if torrent.eta != 8640000:
                        item.eta = format_time(torrent.eta)

                    if item.id:
                        progress_display.update_progress(
                            item.id,
                            f"{item.title[:35]}...",
                            item.downloaded_bytes,
                            item.file_size or 0,
                            item.download_speed or "0 B/s",
                            item.eta or "Unknown",
                            item.progress
                        )

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
                except Exception:
                    time.sleep(3)
                    continue

            return False
        except Exception as e:
            item.status = "failed"
            item.error_message = str(e)[:400]
            self.db.update_download(item, force=True)
            if item.id:
                progress_display.remove_download(item.id)
            return False

