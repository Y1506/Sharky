import hashlib
from pathlib import Path
import pytest

from download_manager.utils import (
    compute_file_hash,
    verify_file_hash,
    validate_url,
    detect_url_type,
    sanitize_filename,
)
from download_manager.downloaders.base import BaseDownloader


def test_checksum_computation_and_verification(tmp_path):
    test_file = tmp_path / "sample.bin"
    content = b"Hello, world! This is a test for checksum verification."
    test_file.write_bytes(content)

    expected_sha256 = hashlib.sha256(content).hexdigest()
    expected_md5 = hashlib.md5(content).hexdigest()

    # Computation
    assert compute_file_hash(test_file, "sha256") == expected_sha256
    assert compute_file_hash(test_file, "md5") == expected_md5

    # Verification
    assert verify_file_hash(test_file, expected_sha256, "sha256") is True
    assert verify_file_hash(test_file, expected_sha256.upper(), "sha256") is True
    assert verify_file_hash(test_file, "wrong_hash_value", "sha256") is False
    assert verify_file_hash(test_file, expected_md5, "md5") is True


def test_url_detection():
    assert detect_url_type("magnet:?xt=urn:btih:d6b63d91b3fa") == "torrent"
    assert detect_url_type("https://example.com/file.torrent") == "torrent"
    assert detect_url_type("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "video"
    assert detect_url_type("https://youtu.be/dQw4w9WgXcQ") == "video"
    assert detect_url_type("https://vimeo.com/123456") == "video"
    assert detect_url_type("https://example.com/archive.zip") == "file"


def test_validate_url():
    assert validate_url("https://example.com/file.zip") is True
    assert validate_url("http://example.com") is True
    assert validate_url("magnet:?xt=urn:btih:abc") is True
    assert validate_url("invalid_url_without_scheme") is False
    assert validate_url("") is False


def test_sanitize_filename():
    assert sanitize_filename("invalid:file*name?.txt") == "invalid_file_name_.txt"
    assert sanitize_filename("normal_file.pdf") == "normal_file.pdf"


def test_rfc5987_content_disposition_extraction():
    # RFC 5987 filename*
    headers_rfc = {"Content-Disposition": "attachment; filename*=UTF-8''special%20filename%20%28test%29.iso"}
    name = BaseDownloader.extract_filename_from_headers(headers_rfc, "fallback.iso")
    assert name == "special filename (test).iso"

    # Standard filename="..."
    headers_std = {"Content-Disposition": 'attachment; filename="package-v1.0.tar.gz"'}
    name = BaseDownloader.extract_filename_from_headers(headers_std, "fallback.tar.gz")
    assert name == "package-v1.0.tar.gz"

    # Fallback when no header
    assert BaseDownloader.extract_filename_from_headers({}, "fallback.bin") == "fallback.bin"
