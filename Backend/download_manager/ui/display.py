import threading
import sys
import time
from typing import Dict, Optional, Union
from ..utils import format_file_size, format_speed, format_time

class ProgressDisplayManager:
    """Multi-task progress display manager with Unicode block progress bars."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._active = False
        self._downloads: Dict[int, dict] = {}
        self._last_render_time = 0.0

    def start(self):
        self._active = True

    def stop(self):
        with self._lock:
            self._active = False
            self._downloads.clear()
            sys.stdout.write('\r\033[K\n')
            sys.stdout.flush()

    def update_progress(
        self,
        item_id: int,
        title: str = "",
        downloaded_bytes: int = 0,
        total_bytes: Optional[int] = 0,
        speed: Union[str, float] = "",
        eta: Optional[str] = None,
        percentage: Optional[float] = None
    ):
        """Update progress for a download item. Handles flexible argument formats."""
        if not self._active:
            self.start()

        # Format / compute speed
        if isinstance(speed, (int, float)):
            speed_val = float(speed)
            speed_str = format_speed(speed_val)
        elif isinstance(speed, str) and speed.strip():
            speed_str = speed.strip()
            speed_val = 0.0
        else:
            speed_str = "0 B/s"
            speed_val = 0.0

        # Calculate percentage if not provided
        total = total_bytes or 0
        if percentage is None:
            if total > 0:
                calc_percentage = min(100.0, max(0.0, (downloaded_bytes / total) * 100))
            else:
                calc_percentage = 0.0
        else:
            calc_percentage = min(100.0, max(0.0, float(percentage)))

        # Calculate ETA if not provided
        if eta is None or eta == "Unknown":
            if total > 0 and speed_val > 0 and downloaded_bytes < total:
                rem_seconds = int((total - downloaded_bytes) / speed_val)
                eta_str = format_time(rem_seconds)
            else:
                eta_str = eta or "Unknown"
        else:
            eta_str = str(eta)

        with self._lock:
            self._downloads[item_id] = {
                'title': title[:30] if title else f"Download #{item_id}",
                'downloaded': downloaded_bytes,
                'total': total,
                'percentage': calc_percentage,
                'speed_str': speed_str,
                'eta_str': eta_str,
                'updated_at': time.time(),
            }
            self._render()

    def _render(self):
        """Render active download progress bar(s)."""
        now = time.time()
        # Limit redraw rate to at most ~10 FPS to avoid terminal flood
        if now - self._last_render_time < 0.08 and len(self._downloads) > 1:
            return
        self._last_render_time = now

        if not self._downloads:
            return

        # If single download, show detailed Unicode block bar
        if len(self._downloads) == 1:
            item = next(iter(self._downloads.values()))
            bar_len = 20
            pct = item['percentage']
            filled = int(bar_len * pct / 100)
            bar = '█' * filled + '░' * (bar_len - filled)

            down_str = format_file_size(item['downloaded'])
            tot_str = format_file_size(item['total']) if item['total'] > 0 else "?"
            line = (
                f"\r\033[KDownloading [{bar}] {pct:.1f}% | "
                f"{down_str}/{tot_str} | {item['speed_str']} | ETA: {item['eta_str']}"
            )
            sys.stdout.write(line)
            sys.stdout.flush()
        else:
            # Multi-download compact view: e.g. [1] 45.2% 1.2 MB/s | [2] 88.0% 3.4 MB/s
            parts = []
            for item_id, item in list(self._downloads.items()):
                tot_str = format_file_size(item['total']) if item['total'] > 0 else "?"
                parts.append(
                    f"#{item_id} [{item['percentage']:.0f}% of {tot_str} @ {item['speed_str']}]"
                )
            line = f"\r\033[KActive ({len(self._downloads)}): " + " | ".join(parts[:4])
            sys.stdout.write(line[:120])
            sys.stdout.flush()

    def render_compact(self) -> str:
        """Return a string summary of active downloads."""
        with self._lock:
            if not self._downloads:
                return ""
            parts = []
            for item_id, item in list(self._downloads.items()):
                parts.append(f"{item['title']} [{item['percentage']:.1f}% @ {item['speed_str']}]")
            return " | ".join(parts)

    def remove_download(self, item_id: int):
        """Clean up completed or failed download."""
        with self._lock:
            if item_id in self._downloads:
                del self._downloads[item_id]
            if not self._downloads:
                sys.stdout.write('\r\033[K')
                sys.stdout.flush()

progress_display = ProgressDisplayManager()
