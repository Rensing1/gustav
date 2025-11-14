"""
Supabase storage adapter — HEAD security hardening.

We verify two properties for the fallback HEAD metadata probe:
- Redirects are not followed (allow_redirects=False)
- Only whitelisted hosts are probed (derived from SUPABASE_PUBLIC_URL/SUPABASE_URL)
"""
from __future__ import annotations

import os
import types
import pytest

from backend.teaching.storage_supabase import SupabaseStorageAdapter


class _FakeBucket:
    def __init__(self, url: str) -> None:
        self._url = url

    def stat(self, key: str):  # force fallback path
        raise AttributeError("no stat in this client")

    def create_signed_url(self, key: str, expires_in: int):
        return {"url": f"{self._url.rstrip('/')}/storage/v1/object/{key}?token=x"}


class _FakeClient:
    def __init__(self, url: str) -> None:
        self._bucket = _FakeBucket(url)

    def from_(self, bucket: str):
        return self._bucket


def test_head_fallback_does_not_follow_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a client that returns a signed URL
    adapter = SupabaseStorageAdapter(_FakeClient("https://app.localhost"))
    # Approve app.localhost as public base so HEAD is attempted
    monkeypatch.setenv("SUPABASE_PUBLIC_URL", "https://app.localhost")

    called = {}

    def fake_head(url, **kwargs):  # type: ignore[no-untyped-def]
        called["allow_redirects"] = kwargs.get("allow_redirects")
        called["timeout"] = kwargs.get("timeout")
        class _R:
            headers = {"content-type": "application/pdf", "content-length": "123"}
        return _R()

    import requests  # type: ignore
    monkeypatch.setattr(requests, "head", fake_head)

    info = adapter.head_object(bucket="b", key="k.pdf")
    assert info["content_type"] == "application/pdf"
    assert called.get("allow_redirects") is False
    assert called.get("timeout") is not None


def test_head_fallback_blocks_non_whitelisted_host(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: no public/internal base configured → unsafe hosts must not be probed
    for var in ("SUPABASE_PUBLIC_URL", "SUPABASE_URL", "SUPABASE_REWRITE_SIGNED_URL_HOST"):
        monkeypatch.delenv(var, raising=False)

    # Client emits a signed URL to an unexpected host
    adapter = SupabaseStorageAdapter(_FakeClient("https://malicious.example"))

    called = {"count": 0}

    def fake_head(url, **kwargs):  # type: ignore[no-untyped-def]
        called["count"] += 1
        class _R:
            headers = {}
        return _R()

    import requests  # type: ignore
    monkeypatch.setattr(requests, "head", fake_head)

    info = adapter.head_object(bucket="b", key="k.pdf")
    # Then: adapter must not perform a HEAD to an unapproved host
    assert called["count"] == 0
    assert info["content_type"] is None and info["content_length"] is None
