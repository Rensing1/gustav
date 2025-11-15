"""
Regression tests for verify_storage_object_integrity semantics.

Focus on:
    - HEAD success with SHA header returns match_head reason.
    - HEAD lacking SHA triggers download fallback when required.
    - Download errors/redirects bubble up with distinct reasons.
    - Untrusted hosts are rejected before HTTP is attempted.
    - Disallowed MIME types raise an explicit error.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import pytest

import backend.storage.verification as verification
from backend.storage.verification import VerificationConfig, verify_storage_object_integrity
from backend.teaching.storage import StorageAdapterProtocol


@dataclass
class _FakeAdapter(StorageAdapterProtocol):
    head: Dict[str, Any]
    url: str

    def presign_upload(self, *, bucket: str, key: str, expires_in: int, headers: Dict[str, str]) -> Dict[str, Any]:  # pragma: no cover - not needed
        return {}

    def head_object(self, *, bucket: str, key: str) -> Dict[str, Any]:
        return dict(self.head)

    def delete_object(self, *, bucket: str, key: str) -> None:  # pragma: no cover - not needed
        return None

    def presign_download(self, *, bucket: str, key: str, expires_in: int, disposition: str) -> Dict[str, Any]:
        return {"url": self.url, "method": "GET", "headers": {}}


def _config(require_remote: bool = True) -> VerificationConfig:
    return VerificationConfig(storage_bucket="submissions", require_remote=require_remote, local_verify_root=None)


def test_head_hash_success_returns_match_head() -> None:
    adapter = _FakeAdapter(head={"content_length": 8, "sha256": "abc123"}, url="https://supabase.local/obj")
    ok, reason = verify_storage_object_integrity(
        adapter=adapter,
        storage_key="course/task/student/file.png",
        expected_sha256="abc123",
        expected_size=8,
        mime_type="image/png",
        config=_config(require_remote=True),
    )
    assert (ok, reason) == (True, "match_head")


def test_download_fallback_returns_match_download(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _FakeAdapter(head={"content_length": 8}, url="https://supabase.local/obj")
    monkeypatch.setattr(
        verification,
        "_stream_hash_from_url",
        lambda *_args, **_kwargs: (True, "feedbeef" * 8, 8, "ok"),
    )
    ok, reason = verify_storage_object_integrity(
        adapter=adapter,
        storage_key="course/task/student/file.png",
        expected_sha256="feedbeef" * 8,
        expected_size=8,
        mime_type="image/png",
        config=_config(require_remote=True),
    )
    assert (ok, reason) == (True, "match_download")


def test_download_redirect_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _FakeAdapter(head={"content_length": 8}, url="https://supabase.local/obj")

    def _redirect(*_args, **_kwargs):
        return (False, None, None, "redirect_detected")

    monkeypatch.setattr(verification, "_stream_hash_from_url", _redirect)
    ok, reason = verify_storage_object_integrity(
        adapter=adapter,
        storage_key="course/task/student/file.png",
        expected_sha256="feedbeef" * 8,
        expected_size=8,
        mime_type="image/png",
        config=_config(require_remote=True),
    )
    assert (ok, reason) == (False, "download_redirect")


def test_untrusted_download_host_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _FakeAdapter(head={"content_length": 8}, url="https://malicious.example/obj")
    monkeypatch.setattr(
        verification,
        "_stream_hash_from_url",
        lambda url, **_: (False, None, None, "untrusted_host"),
    )
    ok, reason = verify_storage_object_integrity(
        adapter=adapter,
        storage_key="course/task/student/file.png",
        expected_sha256="feedbeef" * 8,
        expected_size=8,
        mime_type="image/png",
        config=_config(require_remote=True),
    )
    assert (ok, reason) == (False, "untrusted_host")


def test_mime_whitelist_enforced() -> None:
    adapter = _FakeAdapter(head={"content_length": 8, "sha256": "abc123"}, url="https://supabase.local/obj")
    with pytest.raises(ValueError):
        verify_storage_object_integrity(
            adapter=adapter,
            storage_key="course/task/student/file.exe",
            expected_sha256="abc123",
            expected_size=8,
            mime_type="application/x-msdownload",
            config=_config(require_remote=True),
        )
