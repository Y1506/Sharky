import os
import sys
import time
import subprocess
import xmlrpc.client
import threading
import shutil
from typing import Optional
from rich.console import Console
from ..config import config
from ..models import DownloadItem
from ..database import DatabaseManager
from ..utils import sanitize_filename, format_speed, format_time, format_file_size, compute_file_hash, verify_file_hash
from ..ui.display import progress_display
from .base import BaseDownloader

console = Console()

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
                console.print(f"[yellow]Port {config.ARIA2C_RPC_PORT} is in use but not responding to aria2c RPC[/yellow]")
                return False
        aria2c_path = self.find_aria2c()
        if not aria2c_path:
            console.print("[yellow]aria2c executable not found. Install aria2c for maximum download speed.[/yellow]")
            console.print("[dim]Download from: https://github.com/aria2/aria2/releases[/dim]")
            return False
        console.print(f"[blue]Starting aria2c RPC server on port {config.ARIA2C_RPC_PORT}...[/blue]")
        try:
            download_limit_str = str(config.DOWNLOAD_SPEED_LIMIT) if config.DOWNLOAD_SPEED_LIMIT > 0 else "0"
            upload_limit_str = str(config.UPLOAD_SPEED_LIMIT) if config.UPLOAD_SPEED_LIMIT > 0 else "0"
            continue_str = "true" if config.ARIA2C_CONTINUE else "false"
            bt_save_meta_str = "true" if config.BT_SAVE_MAGNET_AS_TORRENT else "false"
            bt_follow_str = "true" if config.BT_AUTO_DOWNLOAD_CONTENT else "false"
            bt_encrypt_str = "true" if config.BT_FORCE_ENCRYPTION else "false"
            seed_ratio_str = "0.0" if config.BT_KEEP_SEEDING else str(config.BT_SEED_RATIO)
            seed_time_str = "0" if config.BT_KEEP_SEEDING else str(config.BT_SEED_TIME)
            upnp_str = "true" if config.ENABLE_UPNP else "false"
            log_level_str = config.LOG_LEVEL.lower() if config.LOG_LEVEL else "warn"
            if log_level_str not in ["debug", "info", "notice", "warn", "error"]:
                log_level_str = "warn"

            cmd = [
                aria2c_path,
                '--enable-rpc',
                f'--rpc-listen-port={config.ARIA2C_RPC_PORT}',
                f'--rpc-secret={config.ARIA2C_SECRET}',
                '--rpc-listen-all=false',
                f'--max-connection-per-server={config.ARIA2C_MAX_CONNECTIONS}',
                f'--split={config.ARIA2C_SPLIT}',
                f'--min-split-size={config.ARIA2C_MIN_SPLIT_SIZE}',
                f'--max-concurrent-downloads={config.CONCURRENTDOWNLOADS}',
                f'--piece-length={config.ARIA2C_PIECE_LENGTH}',
                f'--disk-cache={config.ARIA2C_DISK_CACHE}',
                f'--file-allocation={config.ARIA2C_FILE_ALLOCATION}',
                f'--continue={continue_str}',
                '--max-tries=20',
                '--retry-wait=0',
                '--timeout=30',
                '--connect-timeout=10',
                '--bt-request-peer-speed-limit=0',
                f'--max-overall-download-limit={download_limit_str}',
                f'--max-download-limit={download_limit_str}',
                f'--max-overall-upload-limit={upload_limit_str}',
                f'--max-upload-limit={upload_limit_str}',
                '--lowest-speed-limit=0',
                '--max-file-not-found=20',
                f'--user-agent={config.USER_AGENT}',
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
                '--enable-dht=true',
                f'--dht-listen-port={config.DHT_LISTEN_PORT}',
                f'--listen-port={config.BT_LISTEN_PORT}',
                f'--enable-rpc-natpmp={upnp_str}',
                '--enable-peer-exchange=true',
                f'--bt-save-metadata={bt_save_meta_str}',
                f'--follow-torrent={bt_follow_str}',
                f'--bt-force-encryption={bt_encrypt_str}',
                '--follow-metalink=false',
                '--metalink-preferred-protocol=http',
                '--bt-enable-lpd=true',
                '--bt-max-peers=55',
                '--bt-stop-timeout=0',
                f'--seed-time={seed_time_str}',
                f'--seed-ratio={seed_ratio_str}',
                f'--log-level={log_level_str}',
                '--console-log-level=error',
                '--summary-interval=0',
                '--download-result=hide',
                '--quiet=true',
            ]

            if config.PROXY_ENABLED and config.PROXY_URL and config.PROXY_URL.strip():
                cmd.append(f'--all-proxy={config.PROXY_URL.strip()}')

            if config.BT_TRACKERS and config.BT_TRACKERS.strip():
                trackers_list = [t.strip() for t in config.BT_TRACKERS.splitlines() if t.strip()]
                if trackers_list:
                    cmd.append(f'--bt-tracker={",".join(trackers_list)}')

            if config.ARIA2_CONF_PATH and os.path.exists(config.ARIA2_CONF_PATH):
                cmd.append(f'--conf-path={config.ARIA2_CONF_PATH}')

            session_file = config.SESSION_PATH or str(config.BASEDIR / 'download.session')
            if session_file:
                cmd.append(f'--save-session={session_file}')
                if os.path.exists(session_file):
                    cmd.append(f'--input-file={session_file}')
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

    def update_runtime_options(self):
        if self.is_running and self.server:
            try:
                dl_limit = str(config.DOWNLOAD_SPEED_LIMIT) if config.DOWNLOAD_SPEED_LIMIT > 0 else "0"
                ul_limit = str(config.UPLOAD_SPEED_LIMIT) if config.UPLOAD_SPEED_LIMIT > 0 else "0"
                options = {
                    "max-overall-download-limit": dl_limit,
                    "max-download-limit": dl_limit,
                    "max-overall-upload-limit": ul_limit,
                    "max-upload-limit": ul_limit,
                    "max-concurrent-downloads": str(config.CONCURRENTDOWNLOADS),
                }
                self.server.aria2.changeGlobalOption(f"token:{config.ARIA2C_SECRET}", options)
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Could not update aria2 runtime options: {e}")

    def restart(self) -> bool:
        self.stop()
        return self.start()

aria2c_manager = Aria2cManager()

class Aria2cDownloader(BaseDownloader):
    def __init__(self, db_manager: DatabaseManager, shutdown_event: threading.Event, pause_event: threading.Event):
        super().__init__(db_manager, shutdown_event, pause_event)

    @property
    def is_available(self) -> bool:
        return aria2c_manager.is_running and aria2c_manager.server is not None

    def download(self, item: DownloadItem, **kwargs) -> bool:
        return self.download_file(item)

    def download_file(self, item: DownloadItem) -> bool:
        if not self.is_available:
            return False
        try:
            if not self.wait_if_paused():
                return False

            if item.download_type == "video":
                output_dir = config.VIDEODIR
            else:
                output_dir = config.FILESDIR
            output_dir.mkdir(parents=True, exist_ok=True)

            filename = self.extract_filename(item.url)
            if not filename or filename == "download.bin":
                filename = f"{sanitize_filename(item.title)}.bin"
            file_path = output_dir / filename
            item.file_path = str(file_path)

            speed_limit = str(config.DOWNLOAD_SPEED_LIMIT) if config.DOWNLOAD_SPEED_LIMIT > 0 else "0"

            options = {
                'dir': str(output_dir),
                'out': filename,
                'max-connection-per-server': str(config.ARIA2C_MAX_CONNECTIONS),
                'split': str(config.ARIA2C_SPLIT),
                'min-split-size': config.ARIA2C_MIN_SPLIT_SIZE,
                'max-concurrent-downloads': '1',
                'piece-length': config.ARIA2C_PIECE_LENGTH,
                'disk-cache': config.ARIA2C_DISK_CACHE,
                'file-allocation': config.ARIA2C_FILE_ALLOCATION,
                'continue': 'true',
                'max-tries': '5',
                'retry-wait': '2',
                'timeout': '60',
                'connect-timeout': '30',
                'max-file-not-found': '5',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'referer': '*',
                'enable-http-keep-alive': 'true',
                'enable-http-pipelining': 'true',
                'enable-mmap': 'true',
                'stream-piece-selector': 'geom',
                'optimize-concurrent-downloads': 'true',
                'max-download-limit': speed_limit,
                'lowest-speed-limit': '0',
                'max-overall-download-limit': '0',
                'conditional-get': 'true',
                'remote-time': 'true',
                'reuse-uri': 'true',
                'max-resume-failure-tries': '5',
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
                if not self.wait_if_paused():
                    return False

                current_time = time.time()
                try:
                    status = aria2c_manager.server.aria2.tellStatus(
                        f"token:{config.ARIA2C_SECRET}", gid,
                        ['totalLength', 'completedLength', 'downloadSpeed', 'connections', 'status', 'errorMessage']
                    )
                except Exception as rpc_err:
                    time.sleep(1)
                    continue

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
                                progress_display.update_progress(
                                    item.id,
                                    f"{item.title[:35]}...",
                                    item.downloaded_bytes,
                                    item.file_size,
                                    avg_speed,
                                    item.eta or "Unknown",
                                    item.progress
                                )
                        last_bytes = item.downloaded_bytes
                        last_time = current_time

                self.db.update_download(item)

                if status['status'] == 'complete':
                    file_path = Path(item.file_path) if item.file_path else None
                    if file_path and file_path.exists():
                        item.file_size = file_path.stat().st_size
                        item.downloaded_bytes = item.file_size
                        item.progress = 100.0
                        item.completed_at = time.strftime('%Y-%m-%d %H:%M:%S')

                        # Checksum verification
                        if item.expected_hash:
                            try:
                                algo = item.hash_algorithm or "sha256"
                                actual = compute_file_hash(file_path, algo)
                                item.actual_hash = actual
                                if actual.strip().lower() != item.expected_hash.strip().lower():
                                    item.status = "failed"
                                    item.error_message = f"Checksum mismatch! Expected: {item.expected_hash}, Actual: {actual}"
                                    self.db.update_download(item, force=True)
                                    if item.id:
                                        progress_display.remove_download(item.id)
                                    console.print(f"[red]X {item.error_message}[/red]")
                                    return False
                            except Exception as hash_err:
                                item.status = "failed"
                                item.error_message = f"Failed to compute hash: {hash_err}"
                                self.db.update_download(item, force=True)
                                if item.id:
                                    progress_display.remove_download(item.id)
                                return False

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

