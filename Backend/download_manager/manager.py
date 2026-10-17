import threading
import time
try:
    import keyboard
    HAS_KEYBOARD = True
except (ImportError, Exception):
    keyboard = None
    HAS_KEYBOARD = False
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Dict
from rich.console import Console

from .config import config
from .models import DownloadItem
from .database import DatabaseManager, Logger
from .network import network_monitor
from .utils import validate_url, detect_url_type, test_connection
from .downloaders import Aria2cDownloader, VideoDownloader, FileDownloader, TorrentDownloader, aria2c_manager
from .ui.display import progress_display

console = Console()

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
        self._reset_orphaned_downloads()
        if config.AUTO_RESUME_UNFINISHED:
            self.start_downloads()

    def _reset_orphaned_downloads(self):
        try:
            downloading = self.db.get_downloads_by_status("downloading")
            paused = self.db.get_downloads_by_status("paused")
            count = 0
            for item in downloading + paused:
                item.status = "pending"
                item.download_speed = None
                item.eta = None
                if self.db.update_download(item, force=True):
                    count += 1
            if count > 0:
                self.logger.info(f"Reset {count} orphaned download(s) to pending status")
        except Exception as e:
            self.logger.error(f"Failed to reset orphaned downloads: {e}")

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

    def add_url(
        self,
        url: str,
        quality: str = "best",
        include_subtitles: bool = False,
        embed_chapters: bool = False,
        expected_hash: Optional[str] = None,
        hash_algorithm: Optional[str] = "sha256",
    ) -> Optional[int]:
        if not validate_url(url):
            console.print(f"[red]X Invalid URL: {url}[/red]")
            return None
        try:
            download_type = detect_url_type(url)
            item = DownloadItem(
                url=url,
                title="Pending...",
                status="pending",
                download_type=download_type,
                quality=quality,
                include_subtitles=include_subtitles,
                embed_chapters=embed_chapters,
                expected_hash=expected_hash.strip().lower() if expected_hash else None,
                hash_algorithm=hash_algorithm.strip().lower() if hash_algorithm else "sha256",
            )
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

    def add_batch_urls(
        self,
        urls: List[str],
        quality: str = "best",
        include_subtitles: bool = False,
        embed_chapters: bool = False,
    ) -> Dict[str, int]:
        """
        Add multiple URLs in a batch.
        Returns a dict with 'added', 'skipped', and 'failed' counts.
        """
        stats = {"added": 0, "skipped": 0, "failed": 0}
        for raw_url in urls:
            url = raw_url.strip()
            if not url or url.startswith("#"):
                continue
            if not validate_url(url):
                stats["failed"] += 1
                continue
            item_id = self.add_url(
                url=url,
                quality=quality,
                include_subtitles=include_subtitles,
                embed_chapters=embed_chapters,
            )
            if item_id is not None:
                stats["added"] += 1
            else:
                stats["skipped"] += 1
        return stats

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
        console.print(f"\n[green]Starting {len(pending)} downloads...[/green]")
        console.print(f"[dim]Concurrent downloads: {parallel_count}[/dim]")
        console.print()

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
        time.sleep(0.5)
        try:
            downloading_items = self.db.get_downloads_by_status("downloading")
            for item in downloading_items:
                item.status = "paused"
                self.db.update_download(item, force=True)
            console.print("[yellow]Downloads paused. Press Ctrl+Shift+R to resume.[/yellow]")
        except Exception as e:
            self.logger.error(f"Failed to pause downloads: {e}")
        self.save_state({'paused': True, 'active_downloads': list(self.active_downloads.keys()), 'timestamp': time.time()})

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
        self.save_state({'paused': False, 'active_downloads': list(self.active_downloads.keys()), 'timestamp': time.time()})

    def _setup_hotkeys(self):
        if not HAS_KEYBOARD or keyboard is None:
            return
        # Skip hotkeys in Docker or non-interactive/headless environments
        import os
        import sys
        if os.environ.get('DOWNLOAD_DIR') or not sys.stdin.isatty():
            return
        try:
            keyboard.add_hotkey(config.PAUSE_HOTKEY, self.pause_downloads)
            keyboard.add_hotkey(config.RESUME_HOTKEY, self.resume_downloads)
        except Exception as e:
            self.logger.debug(f"Could not setup hotkeys: {e}")

    def save_state(self, state_data: dict):
        config.save_state(state_data)

    def load_state(self):
        state = config.load_state()
        if state.get('paused', False):
            self.pause_event.clear()
            console.print("[yellow]Downloads were paused. Press Ctrl+Shift+R to resume.[/yellow]")

    def cleanup(self):
        if HAS_KEYBOARD and keyboard is not None:
            try:
                keyboard.unhook_all()
            except Exception:
                pass
        network_monitor.stop()
        aria2c_manager.stop()
