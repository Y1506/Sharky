import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from download_manager.config import config
import download_manager.api as api_module
from download_manager.models import DownloadItem


@pytest.fixture
def client(tmp_path):
    with patch("download_manager.manager.aria2c_manager"), \
         patch("download_manager.manager.network_monitor"), \
         patch.object(config, "DATABASEFILE", tmp_path / "test_api.db"), \
         patch.object(config, "STATE_FILE", tmp_path / "test_api_state.json"):
        with TestClient(api_module.app) as c:
            yield c


def test_api_add_and_list_downloads(client):
    # Add single download
    resp = client.post("/api/downloads", json={"url": "https://example.com/test_api_file.zip"})
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["message"] == "Download added"

    # List downloads
    list_resp = client.get("/api/downloads")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["url"] == "https://example.com/test_api_file.zip"


def test_api_batch_downloads(client):
    batch_payload = {
        "urls": [
            "https://example.com/batch1.zip",
            "https://example.com/batch2.zip",
            "invalid_url",
        ],
        "quality": "best",
    }
    resp = client.post("/api/downloads/batch", json=batch_payload)
    assert resp.status_code == 200
    stats = resp.json()
    assert stats["added"] == 2
    assert stats["failed"] == 1


def test_api_stats(client):
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    stats = resp.json()
    assert "total" in stats
    assert "pending" in stats
    assert "is_running" in stats
