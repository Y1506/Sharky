import time
import os
import threading
import requests
from rich.console import Console
from ..config import config
from ..models import DownloadItem
from ..database import DatabaseManager
from ..utils import format_speed, format_time, format_file_size, compute_file_hash, verify_file_hash
from ..ui.display import progress_display
from .base import BaseDownloader

console = Console()

class FileDownloader(BaseDownloader):
    def __init__(self, db_manager: DatabaseManager, shutdown_event: threading.Event, pause_event: threading.Event):
        super().__init__(db_manager, shutdown_event, pause_event)

    def download(self, item: DownloadItem, **kwargs) -> bool:
        return self.download_file(item)

    def download_file(self, item: DownloadItem) -> bool:
        try:
            if not self.wait_if_paused():
                return False

            config.FILESDIR.mkdir(parents=True, exist_ok=True)
            
            # Initial preliminary filename guess from URL
            filename = self.extract_filename(item.url)
            file_path = config.FILESDIR / filename

            resume_header = {}
            existing_bytes = 0
            if file_path.exists() and file_path.stat().st_size > 0:
                existing_bytes = file_path.stat().st_size
                resume_header = {'Range': f'bytes={existing_bytes}-'}

            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Connection': 'keep-alive',
            })
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=config.MAXCONNECTIONS,
                pool_maxsize=config.MAXCONNECTIONS,
                max_retries=config.MAXRETRIES,
                pool_block=False
            )
            session.mount('http://', adapter)
            session.mount('https://', adapter)

            response = session.get(item.url, stream=True, timeout=config.TIMEOUT, headers=resume_header, allow_redirects=True)

            # Check if Range was satisfied (206) or full file returned (200)
            if response.status_code == 416:
                # Requested range not satisfiable - file might already be complete
                if file_path.exists() and file_path.stat().st_size > 0:
                    console.print(f"[green]* File already fully downloaded: {filename}[/green]")
                    item.status = "completed"
                    item.progress = 100.0
                    item.file_size = file_path.stat().st_size
                    item.downloaded_bytes = item.file_size
                    item.completed_at = time.strftime('%Y-%m-%d %H:%M:%S')
                    self._check_and_apply_hash(item, file_path)
                    self.db.update_download(item, force=True)
                    return True
                else:
                    response = session.get(item.url, stream=True, timeout=config.TIMEOUT, allow_redirects=True)

            response.raise_for_status()

            # Accurate filename extraction from Content-Disposition and final redirected URL
            real_filename = self.extract_filename(response.url, dict(response.headers))
            if real_filename != filename:
                filename = real_filename
                new_file_path = config.FILESDIR / filename
                if file_path.exists() and file_path != new_file_path:
                    try:
                        file_path.rename(new_file_path)
                    except Exception:
                        pass
                file_path = new_file_path

            item.title = filename
            item.file_path = str(file_path)

            if response.status_code == 206:
                mode = 'ab'
                item.downloaded_bytes = existing_bytes
                content_len = int(response.headers.get('content-length', 0))
                item.file_size = existing_bytes + content_len
                console.print(f"[yellow]Resuming {filename} from {format_file_size(existing_bytes)}[/yellow]")
            else:
                mode = 'wb'
                item.downloaded_bytes = 0
                item.file_size = int(response.headers.get('content-length', 0)) if 'content-length' in response.headers else None

            item.status = "downloading"
            self.db.update_download(item, force=True)
            console.print(f"[blue]Downloading: {filename}[/blue]")

            start_time = time.time()
            start_bytes = item.downloaded_bytes
            last_update_time = start_time

            with open(file_path, mode, buffering=config.BUFFER_SIZE) as f:
                for chunk in response.iter_content(chunk_size=config.CHUNKSIZE):
                    if not self.wait_if_paused():
                        console.print(f"[yellow]Download cancelled: {filename}[/yellow]")
                        return False

                    if chunk:
                        f.write(chunk)
                        item.downloaded_bytes += len(chunk)
                        current_time = time.time()
                        time_since_update = current_time - last_update_time

                        # Bandwidth speed limiter throttling
                        if config.DOWNLOAD_SPEED_LIMIT > 0:
                            transferred = item.downloaded_bytes - start_bytes
                            self.throttle_bandwidth(transferred, start_time, config.DOWNLOAD_SPEED_LIMIT)

                        if time_since_update >= 0.5:
                            avg_speed, speed_str, eta_str = self.update_speed_and_eta(
                                item, current_time, start_time, item.downloaded_bytes, start_bytes
                            )
                            if item.id:
                                progress_display.update_progress(
                                    item.id,
                                    item.title[:35],
                                    item.downloaded_bytes,
                                    item.file_size or 0,
                                    avg_speed,
                                    eta_str,
                                    item.progress
                                )
                            self.db.update_download(item)
                            last_update_time = current_time

            if file_path.exists() and file_path.stat().st_size > 0:
                item.file_size = file_path.stat().st_size
                item.downloaded_bytes = item.file_size
                item.progress = 100.0
                item.completed_at = time.strftime('%Y-%m-%d %H:%M:%S')

                # Verify checksum if requested
                hash_valid = self._check_and_apply_hash(item, file_path)
                if not hash_valid:
                    item.status = "failed"
                    item.error_message = f"Checksum mismatch! Expected: {item.expected_hash}, Actual: {item.actual_hash}"
                    self.db.update_download(item, force=True)
                    if item.id:
                        progress_display.remove_download(item.id)
                    console.print(f"[red]X {item.error_message}[/red]")
                    return False

                item.status = "completed"
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

    def _check_and_apply_hash(self, item: DownloadItem, file_path) -> bool:
        try:
            algo = item.hash_algorithm or "sha256"
            actual = compute_file_hash(file_path, algo)
            item.actual_hash = actual
            if item.expected_hash:
                return actual.strip().lower() == item.expected_hash.strip().lower()
            return True
        except Exception as e:
            if item.expected_hash:
                item.error_message = f"Failed to compute hash: {e}"
                return False
            return True

