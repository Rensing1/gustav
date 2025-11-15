"""
Storage verification — reject non-http/https download URLs.

Given a presigned download URL with an unsupported scheme, the streaming hash
helper must reject it with reason `invalid_url_scheme`.
"""
from __future__ import annotations

from backend.storage.verification import _stream_hash_from_url  # type: ignore


def test_rejects_file_scheme():
    ok, sha, size, reason = _stream_hash_from_url("file:///etc/passwd", timeout=0.1, max_bytes=1024)
    assert ok is False and reason == "invalid_url_scheme"


def test_rejects_ftp_scheme():
    ok, sha, size, reason = _stream_hash_from_url("ftp://example.com/file", timeout=0.1, max_bytes=1024)
    assert ok is False and reason == "invalid_url_scheme"

