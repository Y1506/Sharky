import concurrent.futures
from pathlib import Path
import pytest

from download_manager.database import DatabaseManager
from download_manager.models import DownloadItem


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_downloads.db"
    return DatabaseManager(db_path=db_file)


def test_database_crud_with_hashes(temp_db):
    item = DownloadItem(
        url="https://example.com/test.zip",
        title="Test Zip",
        status="pending",
        download_type="file",
        expected_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        hash_algorithm="sha256",
    )
    item_id = temp_db.add_download(item)
    assert item_id is not None
    assert item_id > 0

    fetched = temp_db.get_download_by_id(item_id)
    assert fetched is not None
    assert fetched.url == "https://example.com/test.zip"
    assert fetched.expected_hash == item.expected_hash
    assert fetched.hash_algorithm == "sha256"
    assert fetched.actual_hash is None

    # Update with actual hash and completion
    fetched.status = "completed"
    fetched.actual_hash = item.expected_hash
    fetched.progress = 100.0
    temp_db.update_download(fetched, force=True)

    updated = temp_db.get_download_by_id(item_id)
    assert updated.status == "completed"
    assert updated.actual_hash == item.expected_hash


def test_duplicate_url_rejection(temp_db):
    item1 = DownloadItem(url="https://example.com/dup.iso", title="Dup 1")
    id1 = temp_db.add_download(item1)
    assert id1 is not None

    item2 = DownloadItem(url="https://example.com/dup.iso", title="Dup 2")
    id2 = temp_db.add_download(item2)
    assert id2 is None


def test_stats_and_removal(temp_db):
    temp_db.add_download(DownloadItem(url="https://example.com/1.bin", status="pending"))
    temp_db.add_download(DownloadItem(url="https://example.com/2.bin", status="downloading"))
    id3 = temp_db.add_download(DownloadItem(url="https://example.com/3.bin", status="completed"))

    stats = temp_db.get_download_stats()
    assert stats["total"] == 3
    assert stats["pending"] == 1
    assert stats["downloading"] == 1
    assert stats["completed"] == 1

    temp_db.remove_downloads([id3])
    assert temp_db.get_download_by_id(id3) is None
    assert temp_db.get_download_stats()["total"] == 2


def test_concurrent_access(temp_db):
    def worker(idx):
        item = DownloadItem(
            url=f"https://example.com/item_{idx}.tar",
            title=f"Item {idx}",
            status="pending",
        )
        item_id = temp_db.add_download(item)
        if item_id:
            fetched = temp_db.get_download_by_id(item_id)
            fetched.progress = 50.0
            temp_db.update_download(fetched, force=True)
            return True
        return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(worker, range(20)))

    assert all(results)
    assert temp_db.get_download_stats()["total"] == 20
