import json
import os
import tempfile
from pathlib import Path
import pytest

from download_manager.config import Config


def test_atomic_json_state_save_and_load(tmp_path):
    cfg = Config()
    cfg.STATE_FILE = tmp_path / "test_state.json"

    test_data = {
        "paused": True,
        "active_downloads": [1, 2, 3],
        "timestamp": 123456789.0,
    }
    cfg.save_state(test_data)

    assert cfg.STATE_FILE.exists()
    loaded = cfg.load_state()
    assert loaded == test_data


def test_load_state_nonexistent_or_corrupted(tmp_path):
    cfg = Config()
    cfg.STATE_FILE = tmp_path / "nonexistent.json"
    assert cfg.load_state() == {}

    # Corrupted file
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("invalid json content!@#")
    cfg.STATE_FILE = corrupt_file
    assert cfg.load_state() == {}


def test_settings_save_and_load(tmp_path):
    cfg = Config()
    cfg.CONFIG_FILE = tmp_path / "test_settings.json"
    cfg.CONCURRENTDOWNLOADS = 8
    cfg.DOWNLOAD_SPEED_LIMIT = 2048576

    cfg.save_settings()
    assert cfg.CONFIG_FILE.exists()

    new_cfg = Config()
    new_cfg.CONFIG_FILE = tmp_path / "test_settings.json"
    new_cfg.load_settings()

    assert new_cfg.CONCURRENTDOWNLOADS == 8
    assert new_cfg.DOWNLOAD_SPEED_LIMIT == 2048576


def test_env_override(monkeypatch, tmp_path):
    custom_dir = str(tmp_path / "custom_downloads")
    monkeypatch.setenv("DOWNLOAD_DIR", custom_dir)
    monkeypatch.setenv("ARIA2C_SECRET", "super_secret_token")

    cfg = Config()
    assert str(cfg.BASEDIR) == custom_dir
    assert cfg.ARIA2C_RPC_SECRET == "super_secret_token"
