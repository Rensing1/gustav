from __future__ import annotations

import os
import pytest

from teaching.storage_supabase import SupabaseStorageAdapter


class _BucketStub:
    def __init__(self, base: str):
        self._base = base.rstrip('/')

    def create_signed_upload_url(self, path: str):
        # Simulate an internal container host returned by Supabase client
        # Shape without /storage/v1 to exercise prefix insertion and upload/sign rewrite
        return {
            "signed_url": f"{self._base}/object/sign/materials/{path}?signature=abc"
        }


class _StorageStub:
    def __init__(self, base: str):
        self._bucket = _BucketStub(base)

    def from_(self, bucket: str):
        return self._bucket


class _SupabaseClientStub:
    def __init__(self, base: str):
        self.storage = _StorageStub(base)


@pytest.mark.anyio
async def test_presign_upload_rewrites_to_public_host(monkeypatch: pytest.MonkeyPatch):
    # Given a public base and a separate internal base
    monkeypatch.setenv("SUPABASE_PUBLIC_URL", "https://app.localhost")
    monkeypatch.setenv("SUPABASE_URL", "http://supabase_kong_gustav-alpha2:8000")
    # No forced rewrite flag should be necessary when PUBLIC is set
    monkeypatch.delenv("SUPABASE_REWRITE_SIGNED_URL_HOST", raising=False)

    client = _SupabaseClientStub(base=os.environ["SUPABASE_URL"])  # type: ignore[index]
    adapter = SupabaseStorageAdapter(client)

    res = adapter.presign_upload(
        bucket="materials",
        key="teacher/unit/section/material/file.pdf",
        expires_in=180,
        headers={"content-type": "application/pdf"},
    )
    from urllib.parse import urlparse
    url = res["url"]
    pu = urlparse(url)
    assert pu.scheme == "https"
    assert pu.hostname == "app.localhost"
    # Path contains bucket and key and correct prefix
    assert pu.path.startswith("/storage/v1/object/upload/sign/")
    assert "/materials/teacher/unit/section/material/file.pdf" in pu.path
