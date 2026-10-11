from abc import ABC, abstractmethod
import os
import re
import threading
import time
from typing import Optional, Tuple
from urllib.parse import urlparse, unquote

from ..config import config
from ..database import DatabaseManager
from ..models import DownloadItem
from ..utils import sanitize_filename, format_speed, format_time, format_file_size
from ..ui.display import progress_display


class BaseDownloader(ABC):
    """Abstract base class for all downloaders, providing shared pause, ETA, bandwidth, and filename handling."""

    def __init__(self, db_manager: DatabaseManager, shutdown_event: threading.Event, pause_event: threading.Event):
        self.db = db_manager
        self.shutdown_event = shutdown_event
        self.pause_event = pause_event

    def wait_if_paused(self) -> bool:
        """
        Blocks while downloads are paused.
        Returns False if shutdown was requested during pause, True otherwise.
        """
        while not self.pause_event.is_set():
            if self.shutdown_event.is_set():
                return False
            time.sleep(0.1)
        return not self.shutdown_event.is_set()

    def is_cancelled(self) -> bool:
        """Check if shutdown/cancellation was requested."""
        return self.shutdown_event.is_set()

    @abstractmethod
    def download(self, item: DownloadItem, **kwargs) -> bool:
        """Perform download for the given DownloadItem."""
        pass

    @classmethod
    def extract_filename_from_headers(cls, response_headers: Optional[dict] = None, fallback: str = "download") -> str:
        """Convenience method to extract filename from headers with a fallback."""
        return cls.extract_filename(fallback, response_headers)

    @classmethod
    def extract_filename(cls, url: str, response_headers: Optional[dict] = None) -> str:
        """
        Extract filename from Content-Disposition header, URL path, or fallback.
        Handles both RFC 5987 (filename*=UTF-8'') and standard filename="name".
        """
        # 1. Try Content-Disposition header if available
        if response_headers:
            cd = response_headers.get('content-disposition', '') or response_headers.get('Content-Disposition', '')
            if cd:
                # Look for filename* (RFC 5987 / UTF-8 encoded)
                fn_match = re.search(r"filename\*\s*=\s*UTF-8''([^;\r\n]+)", cd, re.IGNORECASE)
                if fn_match:
                    try:
                        filename = unquote(fn_match.group(1).strip('"\''))
                        if filename:
                            return sanitize_filename(filename)
                    except Exception:
                        pass

                # Look for standard filename="name" or filename=name
                fn_match = re.search(r'filename\s*=\s*(?:"([^"]+)"|([^;\r\n]+))', cd, re.IGNORECASE)
                if fn_match:
                    raw_fn = fn_match.group(1) or fn_match.group(2)
                    if raw_fn:
                        filename = unquote(raw_fn.strip('"\'\t '))
                        if filename:
                            return sanitize_filename(filename)

        # 2. Extract from URL path
        try:
            parsed = urlparse(url)
            if parsed.path:
                basename = os.path.basename(parsed.path)
                if '?' in basename:
                    basename = basename.split('?')[0]
                basename = unquote(basename).strip()
                if basename and not basename.startswith('.'):
                    return sanitize_filename(basename)
        except Exception:
            pass

        return "download.bin"

    def update_speed_and_eta(
        self,
        item: DownloadItem,
        current_time: float,
        start_time: float,
        current_bytes: int,
        start_bytes: int
    ) -> Tuple[float, str, str]:
        """
        Calculate smoothed speed, ETA, and progress.
        Returns: (speed_bytes_sec, speed_str, eta_str)
        """
        elapsed = current_time - start_time
        bytes_transferred = current_bytes - start_bytes
        speed_bps = bytes_transferred / elapsed if elapsed > 0 else 0.0

        if not hasattr(item, '_speed_samples'):
            item._speed_samples = []  # type: ignore

        item._speed_samples.append(speed_bps)  # type: ignore
        if len(item._speed_samples) > 4:  # type: ignore
            item._speed_samples.pop(0)  # type: ignore

        avg_speed = sum(item._speed_samples) / len(item._speed_samples) if item._speed_samples else 0.0  # type: ignore
        speed_str = format_speed(avg_speed)

        eta_str = "Unknown"
        if item.file_size and item.file_size > current_bytes and avg_speed > 0:
            remaining = item.file_size - current_bytes
            eta_seconds = int(remaining / avg_speed)
            eta_str = format_time(eta_seconds)

        item.download_speed = speed_str
        item.eta = eta_str
        if item.file_size and item.file_size > 0:
            item.progress = min(100.0, (current_bytes / item.file_size) * 100)

        return avg_speed, speed_str, eta_str

    def throttle_bandwidth(
        self,
        transferred_bytes: int = 0,
        session_start_time: float = 0.0,
        speed_limit_bps: int = 0,
        **kwargs
    ) -> float:
        """
        Throttle download if speed exceeds speed_limit_bps.
        speed_limit_bps <= 0 means unlimited.
        Returns the delay applied (in seconds).
        """
        if "speed_limit" in kwargs and not speed_limit_bps:
            speed_limit_bps = kwargs["speed_limit"]
        if "bytes_chunk" in kwargs and not transferred_bytes:
            transferred_bytes = kwargs["bytes_chunk"]
        if "elapsed_chunk" in kwargs and not session_start_time:
            session_start_time = time.time() - kwargs["elapsed_chunk"]

        if speed_limit_bps <= 0 or transferred_bytes <= 0:
            return 0.0

        elapsed = time.time() - session_start_time
        expected_time = transferred_bytes / speed_limit_bps
        sleep_time = expected_time - elapsed
        if sleep_time > 0.01:
            deadline = time.time() + sleep_time
            while time.time() < deadline:
                if self.is_cancelled() or not self.pause_event.is_set():
                    break
                time.sleep(min(0.05, deadline - time.time()))
            return sleep_time
        return 0.0
