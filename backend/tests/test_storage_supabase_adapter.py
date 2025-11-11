from __future__ import annotations

import re

from backend.teaching.storage_supabase import SupabaseStorageAdapter


class _FakeBucket:
    def __init__(self, url: str):
        self._url = url

    def create_signed_upload_url(self, key: str):  # pragma: no cover - simple fake
        # Return the preconstructed URL (simulating a client that embeds path)
        return {"url": self._url}


class _FakeClient:
    def __init__(self, url: str):
        self._bucket = _FakeBucket(url)

    def from_(self, bucket: str):  # storage3 shape
        return self._bucket


def test_presign_upload_collapses_double_slashes_and_forces_upload_sign(monkeypatch):
    # Simulate a client that returns a signed URL with double slashes and legacy sign path
    raw = "http://supabase.local:54321/storage/v1//object/sign/submissions/path/to/file"
    adapter = SupabaseStorageAdapter(_FakeClient(raw))

    res = adapter.presign_upload(bucket="submissions", key="path/to/file", expires_in=600, headers={"Content-Type": "application/pdf"})
    url = res["url"]
    assert "/storage/v1//" not in url  # no double slashes after normalization
    assert "/storage/v1/object/upload/sign/" in url  # forced upload/sign
    # Ensure no accidental triple slashes either
    assert not re.search(r"//{3,}", url)

