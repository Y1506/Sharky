import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from download_manager.downloaders.base import BaseDownloader
from download_manager.downloaders.file import FileDownloader
from download_manager.models import DownloadItem
from download_manager.ui.display import ProgressDisplayManager
from download_manager.database import DatabaseManager


class DummyDownloader(BaseDownloader):
    def download(self, item, **kwargs):
        return True


def test_progress_display_signatures():
    pdm = ProgressDisplayManager()
    # Test 7-arg call (full)
    pdm.update_progress(1, "Test 1", 500, 1000, "100 KB/s", "5s", 50.0)
    # Test 5-arg call (aria2 / torrent style: no eta/percentage explicit)
    pdm.update_progress(2, "Test 2", 1000, 1000, "500 KB/s")
    # Test with string numbers
    pdm.update_progress(3, "Test 3", "200", "400", "50 KB/s", "4s", "50")

    rendered = pdm.render_compact()
    assert "Test 1" in rendered
    assert "Test 2" in rendered
    assert "Test 3" in rendered

    pdm.remove_download(1)
    rendered_after = pdm.render_compact()
    assert "Test 1" not in rendered_after
    assert "Test 2" in rendered_after


def test_base_downloader_bandwidth_throttling():
    shutdown = threading.Event()
    pause = threading.Event()
    pause.set()
    db = MagicMock()
    downloader = DummyDownloader(db, shutdown, pause)

    # Throttling test: limit = 1000 B/s. Downloading 500 bytes took 0.1s.
    # Expected time = 500 / 1000 = 0.5s. Delay = 0.4s.
    with patch("time.sleep") as mock_sleep:
        delay = downloader.throttle_bandwidth(
            bytes_chunk=500,
            elapsed_chunk=0.1,
            speed_limit=1000
        )
        assert delay > 0.35
        mock_sleep.assert_called()


def test_file_downloader_http_range_200_vs_206(tmp_path):
    shutdown = threading.Event()
    pause = threading.Event()
    pause.set()
    db = DatabaseManager(db_path=tmp_path / "test.db")
    downloader = FileDownloader(db, shutdown, pause)

    # Prepare existing partial file
    out_dir = tmp_path / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)
    target_file = out_dir / "test_file.bin"
    target_file.write_bytes(b"initial_bytes_")

    item = DownloadItem(
        url="https://example.com/test_file.bin",
        title="test_file.bin",
        status="pending",
        download_type="file",
    )
    db.add_download(item)

    # Case 1: Server ignores Range header and returns 200 OK with full file content
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = item.url
    mock_resp.headers = {"Content-Length": "12"}
    mock_resp.iter_content = MagicMock(return_value=[b"full_content"])
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.Session.get", return_value=mock_resp):
        with patch("download_manager.config.config.BASEDIR", out_dir), \
             patch("download_manager.config.config.FILESDIR", out_dir):
            success = downloader.download_file(item)

    assert success is True
    # If mode was 'wb' (corrected behavior), the file has b"full_content", NOT b"initial_bytes_full_content"
    assert target_file.read_bytes() == b"full_content"


def test_checksum_verification_on_file_download(tmp_path):
    shutdown = threading.Event()
    pause = threading.Event()
    pause.set()
    db = DatabaseManager(db_path=tmp_path / "test.db")
    downloader = FileDownloader(db, shutdown, pause)
    out_dir = tmp_path / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)

    import hashlib
    file_bytes = b"verification_data_12345"
    correct_hash = hashlib.sha256(file_bytes).hexdigest()

    # Item with correct expected hash
    item = DownloadItem(
        url="https://example.com/verified.bin",
        title="verified.bin",
        status="pending",
        download_type="file",
        expected_hash=correct_hash,
        hash_algorithm="sha256",
    )
    db.add_download(item)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = item.url
    mock_resp.headers = {"Content-Length": str(len(file_bytes))}
    mock_resp.iter_content = MagicMock(return_value=[file_bytes])
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.Session.get", return_value=mock_resp):
        with patch("download_manager.config.config.BASEDIR", out_dir), \
             patch("download_manager.config.config.FILESDIR", out_dir):
            success = downloader.download_file(item)

    assert success is True
    updated = db.get_download_by_id(item.id)
    assert updated.status == "completed"
    assert updated.actual_hash == correct_hash

    # Item with mismatching expected hash
    item_bad = DownloadItem(
        url="https://example.com/bad_hash.bin",
        title="bad_hash.bin",
        status="pending",
        download_type="file",
        expected_hash="0000000000000000000000000000000000000000000000000000000000000000",
        hash_algorithm="sha256",
    )
    db.add_download(item_bad)

    with patch("requests.Session.get", return_value=mock_resp):
        with patch("download_manager.config.config.BASEDIR", out_dir), \
             patch("download_manager.config.config.FILESDIR", out_dir):
            success_bad = downloader.download_file(item_bad)

    assert success_bad is False
    updated_bad = db.get_download_by_id(item_bad.id)
    assert updated_bad.status == "failed"
    assert "Checksum mismatch" in updated_bad.error_message

