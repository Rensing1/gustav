import pytest

from teaching.storage_supabase import SupabaseStorageAdapter


class _BucketStub:
    def __init__(self):
        self.removed = []
        self.calls = {"create_signed_upload_url": [], "create_signed_url": [], "stat": [], "remove": [], "upload": []}

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

    def upload(self, path, body, opts=None):
        self.calls["upload"].append((path, body, dict(opts or {})))
        # emulate success
        return {"data": {"Key": path}}


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


@pytest.mark.anyio
async def test_put_object_calls_upload_with_normalized_key_and_content_type():
    client = _SupabaseClientStub()
    adapter = SupabaseStorageAdapter(client)
    adapter.put_object(
        bucket="materials",
        key="/teacher/unit/section/material/page_0001.png",  # leading slash should be stripped
        body=b"PNG...",
        content_type="image/png",
    )
    calls = client.storage.bucket.calls["upload"]
    assert len(calls) == 1
    path, body, opts = calls[0]
    assert path == "teacher/unit/section/material/page_0001.png"
    assert body == b"PNG..."
    # Accept either option key; adapter sets both for compatibility
    assert opts.get("content-type") == "image/png"
    assert opts.get("contentType") == "image/png"


@pytest.mark.anyio
async def test_put_object_bubbles_up_client_errors():
    class _ErrBucket(_BucketStub):
        def upload(self, path, body, opts=None):  # type: ignore[override]
            raise RuntimeError("upload_failed")

    class _ErrStorage(_StorageStub):
        def __init__(self):
            self.bucket = _ErrBucket()

    class _ErrClient(_SupabaseClientStub):
        def __init__(self):
            self.storage = _ErrStorage()

    client = _ErrClient()
    adapter = SupabaseStorageAdapter(client)
    with pytest.raises(RuntimeError):
        adapter.put_object(
            bucket="materials", key="a/b/c.png", body=b"..", content_type="image/png"
        )
