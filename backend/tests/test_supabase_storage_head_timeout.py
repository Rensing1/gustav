"""
Supabase storage adapter — ensure HEAD fallback uses timeout.

We monkeypatch requests.head and assert it receives a timeout parameter to
prevent hangs during network issues.
"""
from __future__ import annotations

import types
import pytest

from backend.teaching.storage_supabase import SupabaseStorageAdapter


class _FakeBucket:
    def __init__(self) -> None:
        pass

    def stat(self, key: str):  # force fallback path
        raise AttributeError("no stat in this client")

    def create_signed_url(self, key: str, expires_in: int):
        return {"url": f"http://example.local/storage/v1/object/{key}?token=x"}


class _FakeClient:
    def __init__(self) -> None:
        self._bucket = _FakeBucket()

    def from_(self, bucket: str):
        return self._bucket


def test_head_fallback_sets_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = SupabaseStorageAdapter(_FakeClient())

    called = {}

    def fake_head(url, **kwargs):  # type: ignore[no-untyped-def]
        called["url"] = url
        called["timeout"] = kwargs.get("timeout")
        class _R:
            headers = {"content-type": "application/pdf", "content-length": "123"}
        return _R()

    import requests  # type: ignore
    monkeypatch.setattr(requests, "head", fake_head)

    info = adapter.head_object(bucket="b", key="k.pdf")
    assert info["content_type"] == "application/pdf"
    # Timeout must be set to a finite value (e.g., 5 seconds)
    assert isinstance(called.get("timeout"), (int, float))
    assert called["timeout"] and called["timeout"] <= 10

