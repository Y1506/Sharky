import pytest
from unittest.mock import patch, MagicMock

from download_manager.manager import DownloadManager
from download_manager.models import DownloadItem


from download_manager.config import config


@pytest.fixture
def manager(tmp_path):
    with patch("download_manager.manager.aria2c_manager"), \
         patch("download_manager.manager.network_monitor"), \
         patch.object(config, "DATABASEFILE", tmp_path / "test_mgr.db"), \
         patch.object(config, "STATE_FILE", tmp_path / "test_state.json"):
        mgr = DownloadManager()
        yield mgr
        mgr.cleanup()


def test_manager_batch_import(manager):
    urls = [
        "https://example.com/file1.zip",
        "# This is a comment",
        "",
        "https://example.com/file2.zip",
        "invalid-url-format",
        "https://example.com/file1.zip",  # duplicate
    ]

    stats = manager.add_batch_urls(urls)
    assert stats["added"] == 2
    assert stats["skipped"] == 1
    assert stats["failed"] == 1


def test_manager_add_url_with_checksum(manager):
    item_id = manager.add_url(
        url="https://example.com/checksum_test.iso",
        expected_hash="abcdef1234567890",
        hash_algorithm="sha256",
    )
    assert item_id is not None
    item = manager.db.get_download_by_id(item_id)
    assert item.expected_hash == "abcdef1234567890"
    assert item.hash_algorithm == "sha256"
