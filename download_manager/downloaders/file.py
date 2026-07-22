import time
import os
import threading
import requests
from urllib.parse import urlparse
from rich.console import Console
from ..config import config
from ..models import DownloadItem
from ..database import DatabaseManager
from ..utils import sanitize_filename, format_speed, format_time, format_file_size
from ..ui.display import progress_display

console = Console()

class FileDownloader:
    def __init__(self, db_manager: DatabaseManager, shutdown_event: threading.Event, pause_event: threading.Event):
        self.db = db_manager
        self.shutdown_event = shutdown_event
        self.pause_event = pause_event

    def download_file(self, item: DownloadItem) -> bool:
        try:
            if self.shutdown_event.is_set():
                return False
            
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
                pool_connections=config.MAXCONNECTIONS, pool_maxsize=config.MAXCONNECTIONS, max_retries=0, pool_block=False
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
                                progress_display.update_progress(
                                    item.id,
                                    f"{item.title[:40]}...",
                                    item.downloaded_bytes,
                                    item.file_size,
                                    real_speed
                                )
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
