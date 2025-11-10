"""
Unit tests for secure streaming verification when storage HEAD lacks SHA-256.

Covers success, hash mismatch, and size mismatch paths using a fake adapter and
monkeypatched downloader helper.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import pytest

from backend.storage.verification import verify_storage_object_integrity
import backend.storage.verification as verification
from backend.storage.learning_policy import VerificationConfig
from backend.teaching.storage import StorageAdapterProtocol


@dataclass
class _FakeAdapter(StorageAdapterProtocol):
    head: Dict[str, Any]
    url: str

    def presign_upload(self, *, bucket: str, key: str, expires_in: int, headers: Dict[str, str]) -> Dict[str, Any]:  # pragma: no cover - not used
        return {}

    def head_object(self, *, bucket: str, key: str) -> Dict[str, Any]:  # noqa: D401
        return dict(self.head)

    def delete_object(self, *, bucket: str, key: str) -> None:  # pragma: no cover - not used
        return None

    def presign_download(self, *, bucket: str, key: str, expires_in: int, disposition: str) -> Dict[str, Any]:  # noqa: D401
        return {"url": self.url, "method": "GET", "headers": {}}


@pytest.mark.parametrize(
    "ok,actual_sha,actual_size,expected_size,expected_result",
    [
        (True, "a" * 64, 1234, 1234, (True, "ok")),
        (True, "b" * 64, 1234, 1234, (False, "hash_mismatch")),  # will override sha below
        (True, "c" * 64, 1000, 1234, (False, "size_mismatch")),
    ],
)
def test_streaming_verification_paths(monkeypatch, ok, actual_sha, actual_size, expected_size, expected_result):
    # Arrange: HEAD returns only size and an untrusted ETag; no sha headers.
    adapter = _FakeAdapter(head={"content_length": expected_size, "etag": "opaque-etag"}, url="https://storage.test/obj")
    cfg = VerificationConfig(storage_bucket="submissions", require_remote=True, local_verify_root=None)

    # Monkeypatch streaming helper to avoid real HTTP
    sha_for_test = actual_sha
    def fake_stream(url: str, *, timeout: float = 15.0, max_bytes: int = 10 * 1024 * 1024):
        return (ok, sha_for_test, actual_size, "ok" if ok else "download_error")

    monkeypatch.setattr(verification, "_stream_hash_from_url", fake_stream)

    # Use matching/mismatching expected hash depending on case
    expected_sha = actual_sha if expected_result == (True, "ok") else ("z" * 64)

    # Act
    result = verify_storage_object_integrity(
        adapter=adapter,
        storage_key="k",
        expected_sha256=expected_sha,
        expected_size=expected_size,
        mime_type="image/jpeg",
        config=cfg,
    )

    # Assert
    assert result == expected_result

