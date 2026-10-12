import sqlite3
import logging
import sys
import threading
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from .config import config
from .models import DownloadItem

console = Console()

class Logger:
    def __init__(self, logfile: Path):
        self.logger = logging.getLogger('DownloadManager')
        self.logger.setLevel(logging.INFO)
        self.setup_handlers(logfile)

    def setup_handlers(self, logfile: Path):
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        try:
            logfile.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(logfile, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
        except Exception as e:
            console.print(f'[yellow]Warning: Failed to set up file logging: {e}[/yellow]')

    def info(self, message: str):
        self.logger.info(message)

    def warning(self, message: str):
        self.logger.warning(message)

    def error(self, message: str):
        self.logger.error(message)

    def debug(self, message: str):
        self.logger.debug(message)

class DatabaseManager:
    def __init__(self, db_file: Optional[Path] = None, db_path: Optional[Path] = None):
        self.db_file = db_file or db_path or config.DATABASEFILE
        self.logger = Logger(config.LOGFILE)
        self._lock = threading.RLock()
        self._init_database()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_file, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA cache_size=50000")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=268435456")
        return conn

    def _init_database(self):
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS downloads(
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT NOT NULL UNIQUE,
                        title TEXT DEFAULT 'Unknown',
                        download_type TEXT DEFAULT 'unknown',
                        status TEXT DEFAULT 'pending',
                        file_path TEXT,
                        file_size INTEGER,
                        downloaded_bytes INTEGER DEFAULT 0,
                        upload_bytes INTEGER DEFAULT 0,
                        progress REAL DEFAULT 0.0,
                        download_speed TEXT,
                        upload_speed TEXT,
                        eta TEXT,
                        error_message TEXT,
                        attempts INTEGER DEFAULT 0,
                        quality TEXT,
                        include_subtitles INTEGER DEFAULT 0,
                        embed_chapters INTEGER DEFAULT 0,
                        seeds INTEGER DEFAULT 0,
                        peers INTEGER DEFAULT 0,
                        ratio REAL DEFAULT 0.0,
                        expected_hash TEXT,
                        actual_hash TEXT,
                        hash_algorithm TEXT DEFAULT 'sha256',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                ''')
                try:
                    cursor = conn.execute("PRAGMA table_info(downloads)")
                    columns = [row['name'] for row in cursor.fetchall()]
                    if 'upload_bytes' not in columns:
                        conn.execute("ALTER TABLE downloads ADD COLUMN upload_bytes INTEGER DEFAULT 0")
                        self.logger.info("Added upload_bytes column to database")
                    if 'upload_speed' not in columns:
                        conn.execute("ALTER TABLE downloads ADD COLUMN upload_speed TEXT")
                        self.logger.info("Added upload_speed column to database")
                    if 'seeds' not in columns:
                        conn.execute("ALTER TABLE downloads ADD COLUMN seeds INTEGER DEFAULT 0")
                        self.logger.info("Added seeds column to database")
                    if 'peers' not in columns:
                        conn.execute("ALTER TABLE downloads ADD COLUMN peers INTEGER DEFAULT 0")
                        self.logger.info("Added peers column to database")
                    if 'ratio' not in columns:
                        conn.execute("ALTER TABLE downloads ADD COLUMN ratio REAL DEFAULT 0.0")
                        self.logger.info("Added ratio column to database")
                    if 'expected_hash' not in columns:
                        conn.execute("ALTER TABLE downloads ADD COLUMN expected_hash TEXT")
                        self.logger.info("Added expected_hash column to database")
                    if 'actual_hash' not in columns:
                        conn.execute("ALTER TABLE downloads ADD COLUMN actual_hash TEXT")
                        self.logger.info("Added actual_hash column to database")
                    if 'hash_algorithm' not in columns:
                        conn.execute("ALTER TABLE downloads ADD COLUMN hash_algorithm TEXT DEFAULT 'sha256'")
                        self.logger.info("Added hash_algorithm column to database")
                except Exception as e:
                    self.logger.warning(f"Migration check failed: {e}")
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_status ON downloads(status)",
                    "CREATE INDEX IF NOT EXISTS idx_type ON downloads(download_type)",
                    "CREATE INDEX IF NOT EXISTS idx_created ON downloads(created_at)",
                ]
                for index in indexes:
                    conn.execute(index)
                conn.commit()
                self.logger.info("Database initialized successfully")
            except Exception as e:
                self.logger.error(f"Database initialization failed: {e}")
                conn.rollback()
                raise
            finally:
                conn.close()

    def add_download(self, item: DownloadItem) -> Optional[int]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute('''
                    INSERT OR IGNORE INTO downloads 
                    (url, title, download_type, status, quality, include_subtitles, embed_chapters, expected_hash, hash_algorithm)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (item.url, item.title, item.download_type, item.status, item.quality,
                      int(item.include_subtitles), int(item.embed_chapters), item.expected_hash, item.hash_algorithm))
                conn.commit()
                if cursor.rowcount > 0:
                    item.id = cursor.lastrowid
                    return cursor.lastrowid
                return None
            except Exception as e:
                self.logger.error(f"Failed to add download: {e}")
                conn.rollback()
                return None
            finally:
                conn.close()

    def get_download_by_id(self, download_id: int) -> Optional[DownloadItem]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute('SELECT * FROM downloads WHERE id = ?', (download_id,))
                row = cursor.fetchone()
                return self._row_to_item(row) if row else None
            except Exception as e:
                self.logger.error(f"Failed to get download by id: {e}")
                return None
            finally:
                conn.close()

    def update_download(self, item: DownloadItem, force: bool = False) -> bool:
        if not item.id or (not force and not item.should_update_db()):
            return False
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute('''
                    UPDATE downloads SET
                        title = ?, status = ?, file_path = ?, file_size = ?,
                        downloaded_bytes = ?, upload_bytes = ?, progress = ?,
                        download_speed = ?, upload_speed = ?, eta = ?,
                        error_message = ?, attempts = ?, seeds = ?, peers = ?,
                        ratio = ?, actual_hash = ?, completed_at = ?
                    WHERE id = ?
                ''', (item.title, item.status, item.file_path, item.file_size, item.downloaded_bytes, item.upload_bytes, item.progress,
                      item.download_speed, item.upload_speed, item.eta, item.error_message, item.attempts, item.seeds, item.peers,
                      item.ratio, item.actual_hash, item.completed_at, item.id))
                conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                self.logger.error(f"Failed to update download {item.id}: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()

    def get_downloads_by_status(self, status: str, limit: int = 100) -> List[DownloadItem]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute('SELECT * FROM downloads WHERE status = ? ORDER BY created_at DESC LIMIT ?', (status, limit))
                rows = cursor.fetchall()
                return [item for item in [self._row_to_item(row) for row in rows] if item is not None]
            except Exception as e:
                self.logger.error(f"Failed to get downloads by status: {e}")
                return []
            finally:
                conn.close()

    def get_all_downloads(self, limit: int = 100) -> List[DownloadItem]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute('SELECT * FROM downloads ORDER BY created_at DESC LIMIT ?', (limit,))
                rows = cursor.fetchall()
                return [item for item in [self._row_to_item(row) for row in rows] if item is not None]
            except Exception as e:
                self.logger.error(f"Failed to get all downloads: {e}")
                return []
            finally:
                conn.close()

    def get_download_stats(self) -> dict:
        with self._lock:
            conn = self._get_connection()
            try:
                stats = {}
                cursor = conn.execute('SELECT status, COUNT(*) FROM downloads GROUP BY status')
                for row in cursor.fetchall():
                    stats[row[0]] = row[1]
                cursor = conn.execute('SELECT COUNT(*) FROM downloads')
                stats['total'] = cursor.fetchone()[0]
                return stats
            except Exception as e:
                self.logger.error(f"Failed to get stats: {e}")
                return {}
            finally:
                conn.close()

    def remove_downloads(self, download_ids: List[int]) -> int:
        if not download_ids:
            return 0
        with self._lock:
            conn = self._get_connection()
            try:
                placeholders = ','.join(['?' for _ in download_ids])
                cursor = conn.execute(f'DELETE FROM downloads WHERE id IN ({placeholders})', download_ids)
                conn.commit()
                return cursor.rowcount
            except Exception as e:
                self.logger.error(f"Failed to remove downloads: {e}")
                conn.rollback()
                return 0
            finally:
                conn.close()

    def clear_completed_downloads(self) -> int:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute("DELETE FROM downloads WHERE status = 'completed'")
                conn.commit()
                return cursor.rowcount
            except Exception as e:
                self.logger.error(f"Failed to clear completed: {e}")
                conn.rollback()
                return 0
            finally:
                conn.close()

    def clear_failed_downloads(self) -> int:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute("DELETE FROM downloads WHERE status = 'failed'")
                conn.commit()
                return cursor.rowcount
            except Exception as e:
                self.logger.error(f"Failed to clear failed: {e}")
                conn.rollback()
                return 0
            finally:
                conn.close()

    def _row_to_item(self, row) -> Optional[DownloadItem]:
        if not row:
            return None
        try:
            if isinstance(row, sqlite3.Row) or hasattr(row, 'keys'):
                d = dict(row)
                return DownloadItem(
                    id=d.get('id'),
                    url=d.get('url', ''),
                    title=d.get('title', 'Unknown'),
                    download_type=d.get('download_type', 'unknown'),
                    status=d.get('status', 'pending'),
                    file_path=d.get('file_path'),
                    file_size=d.get('file_size'),
                    downloaded_bytes=d.get('downloaded_bytes') or 0,
                    upload_bytes=d.get('upload_bytes') or 0,
                    progress=d.get('progress') or 0.0,
                    download_speed=d.get('download_speed'),
                    upload_speed=d.get('upload_speed'),
                    eta=d.get('eta'),
                    error_message=d.get('error_message'),
                    attempts=d.get('attempts') or 0,
                    quality=d.get('quality'),
                    include_subtitles=bool(d.get('include_subtitles', 0)),
                    embed_chapters=bool(d.get('embed_chapters', 0)),
                    seeds=d.get('seeds') or 0,
                    peers=d.get('peers') or 0,
                    ratio=d.get('ratio') or 0.0,
                    expected_hash=d.get('expected_hash'),
                    actual_hash=d.get('actual_hash'),
                    hash_algorithm=d.get('hash_algorithm') or 'sha256',
                    created_at=d.get('created_at'),
                    completed_at=d.get('completed_at')
                )
            return DownloadItem(
                id=row[0], url=row[1], title=row[2], download_type=row[3], status=row[4], file_path=row[5], file_size=row[6],
                downloaded_bytes=row[7] or 0, upload_bytes=row[8] or 0, progress=row[9] or 0.0, download_speed=row[10], upload_speed=row[11],
                eta=row[12], error_message=row[13], attempts=row[14] or 0, quality=row[15],
                include_subtitles=bool(row[16] if len(row) > 16 else False), embed_chapters=bool(row[17] if len(row) > 17 else False),
                seeds=row[18] if len(row) > 18 else 0, peers=row[19] if len(row) > 19 else 0, ratio=row[20] if len(row) > 20 else 0.0,
                created_at=row[21] if len(row) > 21 else None, completed_at=row[22] if len(row) > 22 else None
            )
        except Exception as e:
            self.logger.error(f"Failed to convert row to item: {e}")
            return None

