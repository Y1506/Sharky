import time
import glob
import os
import sys
import threading
import subprocess
import contextlib
from pathlib import Path
from typing import Optional
from rich.console import Console
import yt_dlp
from ..config import config
from ..models import DownloadItem
from ..database import DatabaseManager
from ..utils import sanitize_filename, format_speed, format_time, format_file_size, check_ffmpeg, compute_file_hash, verify_file_hash
from ..ui.display import progress_display
from ..cookies import CookieManager
from .base import BaseDownloader

console = Console()

class Logger:
 def __init__(self, logfile: Path): pass
 def error(self, msg): pass
 def debug(self, msg): pass
 def info(self, msg): pass

class VideoDownloader(BaseDownloader):
    def __init__(self, db_manager: DatabaseManager, shutdown_event: threading.Event, pause_event: threading.Event):
        super().__init__(db_manager, shutdown_event, pause_event)
        self.logger = Logger(config.LOGFILE)
        self.has_ffmpeg, self.ffmpeg_cmd = check_ffmpeg()
        self.cookie_manager = CookieManager(config)

    def download(self, item: DownloadItem, quality: str = "best") -> bool:
        try:
            if not self.wait_if_paused():
                return False

            # Opportunistic cookie detection: use cookies if available, otherwise proceed
            cookie_method, cookie_value = None, None
            try:
                cookie_result = self.cookie_manager.get_valid_cookies()
                if cookie_result is not None:
                    cookie_method, cookie_value = cookie_result
                else:
                    console.print("[dim]Note: No browser cookies found. Attempting download without cookies...[/dim]")
            except Exception as ce:
                console.print(f"[dim]Cookie check notice: {ce}. Continuing without cookies...[/dim]")

            self._extract_video_info(item)
            is_audio = self._is_audio_only(quality)
            is_playlist = getattr(item, '_is_playlist', False)
            playlist_title = getattr(item, '_playlist_title', None)

            # Determine output directory
            base_output_dir = config.AUDIODIR if is_audio else config.VIDEODIR
            if is_playlist and playlist_title:
                output_dir = base_output_dir / sanitize_filename(playlist_title)
            else:
                output_dir = base_output_dir
            output_dir.mkdir(parents=True, exist_ok=True)

            if is_audio:
                item.include_subtitles = False
                item.embed_chapters = False

            sanitized_title = sanitize_filename(item.title)
            ydl_opts = self._build_ydl_options(
                quality, output_dir, sanitized_title, item,
                is_playlist=is_playlist,
                cookie_method=cookie_method,
                cookie_value=cookie_value,
            )

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

                    if is_playlist:
                        # For playlists, check if the folder has downloaded files
                        downloaded_files = self._find_playlist_files(output_dir, is_audio)
                        if downloaded_files:
                            item.status = "completed"
                            item.progress = 100.0
                            item.file_path = str(output_dir)
                            total_size = sum(f.stat().st_size for f in downloaded_files)
                            item.file_size = total_size
                            item.downloaded_bytes = total_size
                            item.completed_at = time.strftime('%Y-%m-%d %H:%M:%S')
                            self.db.update_download(item, force=True)
                            if item.id:
                                progress_display.remove_download(item.id)
                            console.print(f"[green]* Playlist download completed: {item.title} ({len(downloaded_files)} files)[/green]")
                            console.print(f"[green]  Saved to: {output_dir}[/green]")
                            self._cleanup_temp_files(output_dir, "*")
                            return True
                    else:
                        downloaded_file = self._find_downloaded_file(output_dir, sanitized_title, is_audio)
                        if downloaded_file and downloaded_file.exists():
                            if item.expected_hash:
                                if not self.verify_checksum(downloaded_file, item.expected_hash, item.hash_algorithm or "sha256"):
                                    actual = compute_file_hash(downloaded_file, item.hash_algorithm or "sha256")
                                    item.actual_hash = actual
                                    item.status = "failed"
                                    item.error_message = f"Checksum mismatch: expected {item.expected_hash}, got {actual}"
                                    self.db.update_download(item, force=True)
                                    if item.id:
                                        progress_display.remove_download(item.id)
                                    console.print(f"[red]X {item.error_message}[/red]")
                                    return False
                                item.actual_hash = item.expected_hash

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
                        entries = [e for e in info.get('entries', []) if e]
                        entry_count = len(entries)
                        playlist_title = info.get('title', 'Playlist')
                        item.title = f"{playlist_title} ({entry_count} videos)"
                        # Store playlist metadata for folder creation
                        item._is_playlist = True
                        item._playlist_title = playlist_title
                    else:
                        item.title = info.get('title', 'Unknown Video')[:100]
                        item._is_playlist = False
                        item._playlist_title = None
                    item.title = sanitize_filename(item.title)
                    self.db.update_download(item, force=True)
        except Exception as e:
            self.logger.debug(f"Info extraction failed: {e}")
            item.title = "Unknown Video"
            item._is_playlist = False
            item._playlist_title = None

    def _build_ydl_options(self, quality: str, output_dir: Path, title: str, item: DownloadItem,
                           is_playlist: bool = False, cookie_method: str = None, cookie_value: str = None) -> dict:
        is_audio = self._is_audio_only(quality)
        active_count = len([d for d in self.db.get_downloads_by_status("downloading")])
        if active_count >= 8:
            concurrent_fragments = 32
        elif active_count >= 4:
            concurrent_fragments = 64
        else:
            concurrent_fragments = 128

        # Custom logger to suppress all yt-dlp console output
        class SuppressLogger:
            def debug(self, msg): pass
            def info(self,  msg): pass
            def warning(self, msg): pass
            def error(self, msg): pass

        # Output template: per-video naming for playlists, single file for videos
        if is_playlist:
            # Each playlist video gets: 001 - VideoTitle.ext inside the playlist folder
            outtmpl = str(output_dir / '%(playlist_index)03d - %(title)s.%(ext)s')
        else:
            outtmpl = str(output_dir / f'{title}.%(ext)s')

        ydl_opts = {
            'format': self._get_format_string(quality),
            'outtmpl': outtmpl,
            'no_warnings': True,
            'socket_timeout': 60,
            'retries': 10,
            'fragment_retries': 20,
            'file_access_retries': 10,
            'concurrent_fragment_downloads': concurrent_fragments,
            'http_chunk_size': config.CHUNKSIZE,
            'progress_hooks': [lambda d: self._progress_hook(d, item)],
            'logger': SuppressLogger(),
            'no_check_certificate': True,
            'sleep_interval': 0,
            'max_sleep_interval': 0,
            'no_color': True,
            'quiet': True,
            'no_progress': True,
            'geo_bypass': True,
            'buffer_size': config.BUFFER_SIZE,
            'force_generic_extractor': False,
            'extract_flat': False,
            'skip_unavailable_fragments': True,
            'continue': True,
            'overwrites': True,
            'keepvideo': False,
            'postprocessors': [],
        }

        if config.DOWNLOAD_SPEED_LIMIT > 0:
            ydl_opts['ratelimit'] = config.DOWNLOAD_SPEED_LIMIT

        # --- Playlist-specific options ---
        if is_playlist:
            ydl_opts['ignoreerrors'] = True  # Skip unavailable videos in playlist
            ydl_opts['nooverwrites'] = True  # Don't re-download existing videos

        # --- Cookie injection ---
        if cookie_method == 'file':
            ydl_opts['cookiefile'] = cookie_value
        elif cookie_method == 'browser':
            ydl_opts['cookiesfrombrowser'] = self._parse_browser_spec(cookie_value)

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

    @staticmethod
    def _parse_browser_spec(spec: str):
        """Parse browser spec string into yt-dlp cookiesfrombrowser tuple."""
        parts = spec.split('+')
        main_part = parts[0]
        keyring = None
        container = None

        for extra in parts[1:]:
            if extra.startswith('keyring='):
                keyring = extra.split('=', 1)[1]
            elif extra.startswith('container='):
                container = extra.split('=', 1)[1]

        if ':' in main_part:
            browser_name, profile_path = main_part.split(':', 1)
        else:
            browser_name = main_part
            profile_path = None

        return (browser_name, profile_path, keyring, container)

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
            if 'downloaded_bytes' in d and 'total_bytes' in d and d['total_bytes'] > 0:
                item.downloaded_bytes = d['downloaded_bytes']
                item.file_size = d['total_bytes']
                item.progress = (item.downloaded_bytes / item.file_size) * 100
            elif 'downloaded_bytes' in d and 'total_bytes_estimate' in d and d['total_bytes_estimate'] > 0:
                item.downloaded_bytes = d['downloaded_bytes']
                item.file_size = d['total_bytes_estimate']
                item.progress = (item.downloaded_bytes / item.file_size) * 100
            elif 'fragment_index' in d and 'fragment_count' in d and d.get('fragment_count'):
                item.progress = (d['fragment_index'] / d['fragment_count']) * 100
                if 'downloaded_bytes' in d:
                    item.downloaded_bytes = d['downloaded_bytes']
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
                        # Call progress display with new Unicode block bar signature
                        progress_display.update_progress(
                            item.id,
                            item.title[:40],
                            item.downloaded_bytes,
                            item.file_size,
                            item.download_speed or "0 B/s",
                            item.eta or "Unknown",
                            item.progress
                        )
                    item._last_speed_update = current_time
                    item._real_start_bytes = item.downloaded_bytes
            if item.should_update_db(threshold=0.5):
                self.db.update_download(item, force=True)

    def _find_downloaded_file(self, output_dir: Path, title: str, is_audio: bool) -> Optional[Path]:
        extensions = ['.m4a', '.mp3'] if is_audio else ['.mp4', '.mkv', '.webm']
        for ext in extensions:
            file_path = output_dir / f"{title}{ext}"
            if file_path.exists() and file_path.stat().st_size > 0:
                return file_path
        return None

    def _find_playlist_files(self, playlist_dir: Path, is_audio: bool) -> list:
        """Find all downloaded media files in a playlist directory."""
        if not playlist_dir.exists():
            return []
        extensions = {'.m4a', '.mp3'} if is_audio else {'.mp4', '.mkv', '.webm'}
        found = []
        for f in playlist_dir.iterdir():
            if f.is_file() and f.suffix.lower() in extensions and f.stat().st_size > 0:
                found.append(f)
        return sorted(found)

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
