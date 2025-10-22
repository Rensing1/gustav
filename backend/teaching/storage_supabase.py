"""
Supabase-backed storage adapter for teaching materials.

This adapter implements StorageAdapterProtocol using a provided Supabase client.
It is intentionally duck-typed to avoid a hard dependency during testing. The
client is expected to expose `.storage.from_(bucket)` which returns an object
offering:

- create_signed_upload_url(path) -> { signed_url | signedURL | url }
- create_signed_url(path, expires_in, options=None) -> { signed_url | signedURL | url, expires_at? }
- stat(path) -> { size, mimetype }
- remove([path]) -> Any

Security:
- The caller must ensure the client is initialized with the Service Role key.
- All buckets should be private; clients receive only short-lived signed URLs.
"""
from __future__ import annotations

from typing import Any, Dict

from .storage import StorageAdapterProtocol


class SupabaseStorageAdapter(StorageAdapterProtocol):
    """Storage adapter using a supabase client for Storage operations."""

    def __init__(self, client: Any):
        # Duck-typed supabase client, e.g., from `supabase import create_client(...)`.
        self._client = client

    # --- Helpers -----------------------------------------------------------------

    def _bucket(self, bucket: str) -> Any:
        return self._client.storage.from_(bucket)

    @staticmethod
    def _first_key(d: Dict[str, Any], *keys: str) -> Any:
        for k in keys:
            if k in d and d[k] is not None:
                return d[k]
        return None

    # --- Protocol methods --------------------------------------------------------

    def presign_upload(self, *, bucket: str, key: str, expires_in: int, headers: Dict[str, str]) -> Dict[str, Any]:
        b = self._bucket(bucket)
        # Supabase signed upload URLs usually do not take expires_in on this call;
        # TTL is encoded in the signed URL/token server-side.
        res = b.create_signed_upload_url(key)
        # Normalize field names across potential library versions.
        url = None
        if isinstance(res, dict):
            url = self._first_key(res, "url", "signed_url", "signedURL")
            data = res.get("data") if "data" in res else None
            if url is None and isinstance(data, dict):
                url = self._first_key(data, "url", "signed_url", "signedURL")
        if not url:
            # Best-effort fallback: some clients return a tuple (data, error)
            try:
                data = res[0] if isinstance(res, (list, tuple)) else None
                if isinstance(data, dict):
                    url = self._first_key(data, "url", "signed_url", "signedURL")
            except Exception:
                pass
        if not url:
            raise RuntimeError("failed_to_presign_upload")
        # Backend expects to echo any headers (e.g., content-type) back to the client.
        return {"url": str(url), "headers": dict(headers or {})}

    def head_object(self, *, bucket: str, key: str) -> Dict[str, Any]:
        b = self._bucket(bucket)
        info = b.stat(key)
        size = None
        mime = None
        if isinstance(info, dict):
            # supabase-py v2 typically reports `size` and `mimetype` keys
            size = info.get("size")
            mime = info.get("mimetype") or info.get("content_type")
        return {"content_length": size, "content_type": mime}

    def delete_object(self, *, bucket: str, key: str) -> None:
        b = self._bucket(bucket)
        # Supabase Storage remove expects a list of paths
        b.remove([key])

    def presign_download(self, *, bucket: str, key: str, expires_in: int, disposition: str) -> Dict[str, Any]:
        b = self._bucket(bucket)
        # Some clients accept an options dict to influence content-disposition via `download` param.
        # We provide a hint but servers may ignore it; our API consumes only the URL + expires.
        opts = {"download": None if disposition == "inline" else key.split("/")[-1]}
        res = b.create_signed_url(key, expires_in, opts)
        url = None
        expires_at = None
        if isinstance(res, dict):
            url = self._first_key(res, "url", "signed_url", "signedURL")
            expires_at = self._first_key(res, "expires_at", "expiresAt")
            data = res.get("data") if "data" in res else None
            if (url is None or expires_at is None) and isinstance(data, dict):
                url = url or self._first_key(data, "url", "signed_url", "signedURL")
                expires_at = expires_at or self._first_key(data, "expires_at", "expiresAt")
        if not url:
            try:
                data = res[0] if isinstance(res, (list, tuple)) else None
                if isinstance(data, dict):
                    url = self._first_key(data, "url", "signed_url", "signedURL")
                    expires_at = expires_at or self._first_key(data, "expires_at", "expiresAt")
            except Exception:
                pass
        if not url:
            raise RuntimeError("failed_to_presign_download")
        return {"url": str(url), "expires_at": expires_at}


__all__ = ["SupabaseStorageAdapter"]

