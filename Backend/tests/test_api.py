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


def test_api_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["app"] == "Sharky"

    resp2 = client.get("/health")
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "ok"


def test_api_settings_get_and_update(client, tmp_path):
    get_resp = client.get("/api/settings")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert "download_dir" in data
    assert "concurrent_downloads" in data
    assert "download_speed_limit" in data

    # Update settings
    new_dir = str(tmp_path / "custom_downloads")
    update_resp = client.put(
        "/api/settings",
        json={
            "download_dir": new_dir,
            "concurrent_downloads": 8,
            "download_speed_limit": 1048576,
            "aria2c_rpc_port": 6801,
        },
    )
    assert update_resp.status_code == 200
    updated_data = update_resp.json()["settings"]
    assert updated_data["concurrent_downloads"] == 8
    assert updated_data["download_speed_limit"] == 1048576
    assert updated_data["aria2c_rpc_port"] == 6801

    # Validation errors
    bad_resp = client.put("/api/settings", json={"concurrent_downloads": 0})
    assert bad_resp.status_code == 400

    bad_speed = client.put("/api/settings", json={"download_speed_limit": -1})
    assert bad_speed.status_code == 400


def test_api_cookies_status_and_clear(client):
    status_resp = client.get("/api/settings/cookies/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert "has_cached_cookies" in status_data

    clear_resp = client.post("/api/settings/cookies/clear")
    assert clear_resp.status_code == 200


