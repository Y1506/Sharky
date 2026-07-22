import sys
import signal
import threading
from typing import List
from rich.console import Console
from rich.table import Table

from ..config import config
from ..models import DownloadItem
from ..database import Logger
from ..network import network_monitor
from ..utils import detect_url_type, check_ffmpeg, format_file_size
from ..downloaders import aria2c_manager
from ..manager import DownloadManager
from ..cookies import CookieManager

console = Console()

class CLI:
    def __init__(self):
        self.manager = DownloadManager()
        self.logger = Logger(config.LOGFILE)
        self.cookie_manager = CookieManager(config)
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
        console.print("Advanced Download Manager v2.3 - Modular & Enhanced".center(70))
        console.print("aria2c Auto-Launch | Real Speed Tracking".center(70))
        console.print("=" * 70 + "\n")
        console.print("[dim]Initializing system components...[/dim]")
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
                # qBittorrent check omitted for brevity in banner, checked on demand
                speeds = network_monitor.get_speeds()
                net_status = f"[green]* Active (DOWN {speeds['download']} | UP {speeds['upload']})[/green]"
                # Cookie status
                cookie_status_info = self.cookie_manager.get_cookie_status()
                if cookie_status_info['has_cached_cookies'] and cookie_status_info['cached_cookie_fresh']:
                    cookie_status = f"[green]* Cached (age: {cookie_status_info['cached_cookie_age']})[/green]"
                elif cookie_status_info['has_cached_cookies']:
                    cookie_status = f"[yellow]! Stale (age: {cookie_status_info['cached_cookie_age']})[/yellow]"
                else:
                    cookie_status = "[yellow]! No cached cookies[/yellow]"
                browsers = []
                if cookie_status_info['zen_available']:
                    browsers.append('Zen')
                if cookie_status_info['brave_available']:
                    browsers.append('Brave')
                if browsers:
                    cookie_status += f" [dim](Browsers: {', '.join(browsers)})[/dim]"
                self._system_status = {
                    'ffmpeg': ffmpeg_status, 'aria2c': aria2c_status,
                    'network': net_status, 'cookies': cookie_status
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
            console.print(f"  Network: [green]DOWN {speeds['download']} | UP {speeds['upload']}[/green]")
            console.print(f"  Cookies: {self._system_status.get('cookies', '[dim]Checking...[/dim]')}")
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
            console.print("[dim]Downloads are running in the background. Use 'View Downloads' to monitor progress.[/dim]")
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
            ids_input = console.input("[bold]Enter download IDs to remove (comma-separated):[/bold] ").strip()
            try:
                ids = [int(x.strip()) for x in ids_input.split(',') if x.strip()]
                count = self.manager.remove_downloads(ids)
                console.print(f"[green]* Removed {count} downloads[/green]")
            except ValueError:
                console.print("[red]X Invalid ID format[/red]")

    def _settings_menu(self):
        console.clear()
        console.print("[bold cyan]Settings[/bold cyan]\n")
        console.print("[bold]1.[/bold] Change Download Directory")
        console.print("[bold]2.[/bold] Change Concurrent Downloads")
        console.print("[bold]3.[/bold] View Current Settings")
        console.print("[bold]4.[/bold] Cookie Settings")
        choice = console.input("\n[bold]Choice:[/bold] ").strip()

        if choice == '1':
            new_path = console.input("[bold]Enter new download directory path:[/bold] ").strip()
            if new_path:
                if config.set_download_directory(new_path):
                    console.print(f"[green]* Download directory changed to: {new_path}[/green]")
                else:
                    console.print("[red]X Failed to change directory[/red]")
        elif choice == '2':
            new_val = console.input(f"[bold]New value (1-32):[/bold] ").strip()
            try:
                val = int(new_val)
                if 1 <= val <= 32:
                    config.CONCURRENTDOWNLOADS = val
                    config.save_settings()
                    console.print(f"\n[green]* Concurrent downloads set to {val}[/green]")
            except ValueError:
                console.print("[red]X Invalid number[/red]")
        elif choice == '3':
            console.print(f"Download Directory: {config.BASEDIR}")
            console.print(f"Concurrent Downloads: {config.CONCURRENTDOWNLOADS}")
            console.print(f"Cookie Manual Path: {config.COOKIE_MANUAL_PATH or 'Auto'}")
            console.print(f"Cookie Browser Path: {config.COOKIE_BROWSER_PATH or 'Auto'}")
            console.print(f"Cookie Max Age: {config.COOKIE_MAX_AGE}s ({config.COOKIE_MAX_AGE // 3600}h)")
            console.print(f"Cookie Browser Order: {', '.join(config.COOKIE_BROWSER_ORDER)}")
        elif choice == '4':
            self._cookie_settings_menu()

    def _cookie_settings_menu(self):
        console.print("\n[bold cyan]Cookie Settings[/bold cyan]\n")
        status = self.cookie_manager.get_cookie_status()
        console.print("[dim]Current Status:[/dim]")
        console.print(f"  Cached cookies: {'Yes' if status['has_cached_cookies'] else 'No'}")
        if status['has_cached_cookies']:
            freshness = '[green]Fresh[/green]' if status['cached_cookie_fresh'] else '[yellow]Stale[/yellow]'
            console.print(f"  Cookie age: {status['cached_cookie_age']} ({freshness})")
        console.print(f"  Manual cookie path: {status['manual_path'] or 'Not set (auto)'}")
        console.print(f"  Zen Browser: {'[green]Found[/green]' if status['zen_available'] else '[red]Not found[/red]'}")
        console.print(f"  Brave Browser: {'[green]Found[/green]' if status['brave_available'] else '[red]Not found[/red]'}")
        console.print()
        console.print("[bold]1.[/bold] Set Manual Cookie File Path")
        console.print("[bold]2.[/bold] Set Manual Browser Profile Path")
        console.print("[bold]3.[/bold] Force Re-extract Cookies")
        console.print("[bold]4.[/bold] Clear Cached Cookies")
        console.print("[bold]5.[/bold] Reset to Auto")
        sub_choice = console.input("\n[bold]Choice:[/bold] ").strip()
        if sub_choice == '1':
            path = console.input("[bold]Enter cookie file path (Netscape format):[/bold] ").strip()
            if path:
                config.COOKIE_MANUAL_PATH = path
                config.save_settings()
                console.print(f"[green]* Manual cookie path set to: {path}[/green]")
        elif sub_choice == '2':
            path = console.input("[bold]Enter browser profile directory path:[/bold] ").strip()
            if path:
                config.COOKIE_BROWSER_PATH = path
                config.save_settings()
                console.print(f"[green]* Browser profile path set to: {path}[/green]")
        elif sub_choice == '3':
            console.print("[blue]Re-extracting cookies...[/blue]")
            self.cookie_manager.clear_cached_cookies()
            result = self.cookie_manager.get_valid_cookies()
            if result:
                console.print(f"[green]* Cookies extracted successfully (method: {result[0]})[/green]")
            else:
                console.print("[red]X Failed to extract cookies[/red]")
        elif sub_choice == '4':
            self.cookie_manager.clear_cached_cookies()
        elif sub_choice == '5':
            config.COOKIE_MANUAL_PATH = None
            config.COOKIE_BROWSER_PATH = None
            config.save_settings()
            console.print("[green]* Cookie settings reset to auto[/green]")

    def _exit(self):
        console.print("[yellow]Shutting down...[/yellow]")
        self.manager.stop_downloads()
        self.manager.cleanup()
        self.running = False
        console.print("[green]Goodbye![/green]")
        sys.exit(0)
