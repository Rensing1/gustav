import pytest

from teaching.storage_supabase import SupabaseStorageAdapter


class _BucketStub:
    def __init__(self):
        self.removed = []
        self.calls = {"create_signed_upload_url": [], "create_signed_url": [], "stat": [], "remove": []}

    def create_signed_upload_url(self, path):
        self.calls["create_signed_upload_url"].append(path)
        return {"signed_url": f"http://supabase.local/upload/{path}"}

    def stat(self, path):
        self.calls["stat"].append(path)
        return {"size": 1024, "mimetype": "application/pdf; charset=utf-8"}

    def create_signed_url(self, path, expires_in, opts=None):
        self.calls["create_signed_url"].append((path, expires_in, opts))
        return {"signed_url": f"http://supabase.local/object/{path}", "expires_at": "2025-10-22T12:34:56Z"}

    def remove(self, paths):
        self.calls["remove"].append(list(paths))
        self.removed.extend(paths)
        return {"data": {"removed": list(paths)}}


class _StorageStub:
    def __init__(self):
        self.bucket = _BucketStub()

    def from_(self, bucket):
        # For this adapter, we don't branch per bucket; we return a bucket impl.
        return self.bucket


class _SupabaseClientStub:
    def __init__(self):
        self.storage = _StorageStub()


@pytest.mark.anyio
async def test_presign_upload_returns_url_and_headers():
    client = _SupabaseClientStub()
    adapter = SupabaseStorageAdapter(client)
    res = adapter.presign_upload(
        bucket="materials",
        key="teacher/unit/section/material/file.pdf",
        expires_in=180,
        headers={"content-type": "application/pdf"},
    )
    assert res["url"].startswith("http://supabase.local/upload/")
    assert res["headers"]["content-type"] == "application/pdf"


@pytest.mark.anyio
async def test_head_object_maps_metadata_fields():
    client = _SupabaseClientStub()
    adapter = SupabaseStorageAdapter(client)
    head = adapter.head_object(bucket="materials", key="path/to/file.pdf")
    assert head["content_length"] == 1024
    assert head["content_type"].startswith("application/pdf")


@pytest.mark.anyio
async def test_presign_download_returns_url_and_expiry():
    client = _SupabaseClientStub()
    adapter = SupabaseStorageAdapter(client)
    res = adapter.presign_download(
        bucket="materials",
        key="teacher/unit/section/material/file.pdf",
        expires_in=45,
        disposition="inline",
    )
    assert res["url"].startswith("http://supabase.local/object/")
    assert res["expires_at"] == "2025-10-22T12:34:56Z"


@pytest.mark.anyio
async def test_delete_object_invokes_remove():
    client = _SupabaseClientStub()
    adapter = SupabaseStorageAdapter(client)
    adapter.delete_object(bucket="materials", key="teacher/unit/section/material/file.pdf")
    assert client.storage.bucket.removed == ["teacher/unit/section/material/file.pdf"]

