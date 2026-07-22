import threading
import sys
from typing import Dict

class ProgressDisplayManager:
    """Progress display with Unicode block progress bars"""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._active = False

    def start(self):
        self._active = True

    def stop(self):
        self._active = False

    def update_progress(self, item_id: int, title: str, downloaded_bytes: int, total_bytes: int, speed: str, eta: str, percentage: float):
        """Print progress with Unicode block characters"""
        if not self._active:
            self.start()
        
        with self._lock:
            # Create Unicode block progress bar [████████████░░░░░░░░]
            bar_length = 20
            filled = int(bar_length * percentage / 100)
            # Use block characters: █ for filled, ░ for empty
            bar = '█' * filled + '░' * (bar_length - filled)
            
            # Format bytes in readable format
            def format_bytes(b):
                if b >= 1024**3:
                    return f"{b / 1024**3:.1f} GB"
                elif b >= 1024**2:
                    return f"{b / 1024**2:.1f} MB"
                elif b >= 1024:
                    return f"{b / 1024:.1f} KB"
                return f"{b} B"
            
            downloaded_str = format_bytes(downloaded_bytes)
            total_str = format_bytes(total_bytes)
            
            # Format: Downloading: [████████████░░░░░░░░] 1.2/2.0 GB (58.5%) 1.2 MB/s [ETA 45s]
            progress_line = f"\rDownloading: [{bar}] {downloaded_str}/{total_str} ({percentage:.1f}%) {speed} [ETA {eta}]"
            
            # Clear to end of line and print
            sys.stdout.write('\033[K')  # Clear to end of line
            sys.stdout.write(progress_line)
            sys.stdout.flush()

    def remove_download(self, item_id: int):
        """Move to new line when download completes"""
        with self._lock:
            sys.stdout.write('\n')
            sys.stdout.flush()

progress_display = ProgressDisplayManager()
