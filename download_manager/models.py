from dataclasses import dataclass, field
from typing import Optional, List
import time

@dataclass
class DownloadItem:
    id: Optional[int] = None
    url: str = ""
    title: str = "Unknown"
    download_type: str = "unknown"
    status: str = "pending"
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    downloaded_bytes: int = 0
    upload_bytes: int = 0
    progress: float = 0.0
    download_speed: Optional[str] = None
    upload_speed: Optional[str] = None
    eta: Optional[str] = None
    error_message: Optional[str] = None
    attempts: int = 0
    quality: Optional[str] = None
    include_subtitles: bool = False
    embed_chapters: bool = False
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    seeds: int = 0
    peers: int = 0
    ratio: float = 0.0
    expected_hash: Optional[str] = None
    actual_hash: Optional[str] = None
    hash_algorithm: str = "sha256"
    _last_update: float = field(default_factory=time.time)
    _real_start_time: Optional[float] = None
    _real_start_bytes: int = 0
    _last_speed_update: float = field(default_factory=time.time)
    _speed_window: List[float] = field(default_factory=list)

    def should_update_db(self, threshold: float = 0.5) -> bool:
        now = time.time()
        if now - self._last_update >= threshold:
            self._last_update = now
            return True
        return False

    @property
    def progress_percentage(self) -> int:
        return int(min(100, max(0, self.progress)))
