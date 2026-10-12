import threading
import time
import psutil
from typing import Dict, Union
from .utils import format_speed

class NetworkMonitor:
    def __init__(self):
        self.download_speed = 0.0
        self.upload_speed = 0.0
        self.monitoring = False
        self._thread = None
        self._lock = threading.Lock()
        self.speed_history = []

    def start(self):
        if self.monitoring:
            return
        self.monitoring = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.monitoring = False
        if self._thread:
            self._thread.join(timeout=2)

    def _monitor_loop(self):
        try:
            old_value = psutil.net_io_counters()
            old_time = time.time()
            while self.monitoring:
                time.sleep(0.5)
                new_value = psutil.net_io_counters()
                new_time = time.time()
                time_diff = new_time - old_time
                if time_diff > 0:
                    download_diff = new_value.bytes_recv - old_value.bytes_recv
                    upload_diff = new_value.bytes_sent - old_value.bytes_sent
                    instant_download = download_diff / time_diff
                    instant_upload = upload_diff / time_diff
                    with self._lock:
                        self.speed_history.append((instant_download, instant_upload))
                        if len(self.speed_history) > 3:
                            self.speed_history.pop(0)
                        if self.speed_history:
                            avg_down = sum(s[0] for s in self.speed_history) / len(self.speed_history)
                            avg_up = sum(s[1] for s in self.speed_history) / len(self.speed_history)
                            self.download_speed = avg_down
                            self.upload_speed = avg_up
                old_value = new_value
                old_time = new_time
        except Exception:
            pass

    def get_speeds(self) -> Dict[str, Union[str, float]]:
        with self._lock:
            return {
                'download': format_speed(self.download_speed),
                'upload': format_speed(self.upload_speed),
                'download_bytes': self.download_speed,
                'upload_bytes': self.upload_speed
            }

network_monitor = NetworkMonitor()
