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
import os
from urllib.parse import urlparse as _urlparse, urlunparse as _urlunparse

from .storage import StorageAdapterProtocol


class SupabaseStorageAdapter(StorageAdapterProtocol):
    """Storage adapter using a supabase client for Storage operations."""

    def __init__(self, client: Any):
        # Duck-typed supabase client, e.g., from `supabase import create_client(...)`.
        self._client = client

    # --- Helpers -----------------------------------------------------------------

    def _bucket(self, bucket: str) -> Any:
        """Return a bucket proxy from either supabase client or storage3 client.

        Supports two client shapes:
        - supabase.create_client(...): expose `.storage.from_(bucket)`
        - storage3 SyncStorageClient: expose `.from_(bucket)` directly
        """
        c = self._client
        try:
            storage = getattr(c, "storage", None)
            if storage is not None and hasattr(storage, "from_"):
                return storage.from_(bucket)
            if hasattr(c, "from_"):
                return c.from_(bucket)  # type: ignore[attr-defined]
        except Exception:
            pass
        raise RuntimeError("invalid_supabase_client")

    @staticmethod
    def _first_key(d: Dict[str, Any], *keys: str) -> Any:
        for k in keys:
            if k in d and d[k] is not None:
                return d[k]
        return None

    # --- Protocol methods --------------------------------------------------------

    def presign_upload(self, *, bucket: str, key: str, expires_in: int, headers: Dict[str, str]) -> Dict[str, Any]:
        b = self._bucket(bucket)
        # Normalize key to be relative to the bucket (storage3 prepends the bucket id)
        norm_key = key.lstrip("/")
        prefix = f"{bucket}/"
        if norm_key.startswith(prefix):
            norm_key = norm_key[len(prefix):]
        # Supabase signed upload URLs usually do not take expires_in on this call;
        # TTL is encoded in the signed URL/token server-side.
        res = b.create_signed_upload_url(norm_key)
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
        # Normalize host and path for local dev; ensure modern upload-sign path.
        url = self._normalize_signed_url_host(str(url))
        try:
            from urllib.parse import urlparse as _p, urlunparse as _u
            p = _p(url)
            path = p.path or "/"
            # Ensure /storage/v1 prefix
            if path.startswith("/object/"):
                path = "/storage/v1" + path
            # Force upload/sign endpoint shape for PUT
            path = path.replace("/storage/v1/object/sign/", "/storage/v1/object/upload/sign/")
            url = _u((p.scheme, p.netloc, path, p.params, p.query, p.fragment))
        except Exception:
            pass
        # As a last resort (flaky client variants), regenerate via storage3 to guarantee upload/sign
        try:
            from urllib.parse import urlparse as _p
            force = (os.getenv("SUPABASE_REWRITE_SIGNED_URL_HOST", "false").lower() == "true")
            base = (os.getenv("SUPABASE_URL") or "").strip()
            signed = _p(url)
            base_p = _p(base) if base else None
            same_host = bool(base_p and signed.hostname and base_p.hostname and (signed.hostname == base_p.hostname))
            if (force or same_host) and "/object/upload/sign/" not in signed.path:
                key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
                if base and key:
                    from storage3._sync.client import SyncStorageClient  # type: ignore
                    storage_client = SyncStorageClient(base.rstrip('/') + "/storage/v1", {"Authorization": f"Bearer {key}", "apikey": key})
                    new_url = storage_client.from_(bucket).create_signed_upload_url(norm_key)
                    if isinstance(new_url, dict):
                        candidate = new_url.get("signed_url") or new_url.get("url")
                        if candidate:
                            url = str(candidate)
        except Exception:
            pass
        # Backend expects to echo any headers (e.g., content-type) back to the client.
        # Normalize header keys to lowercase to keep API stable across clients.
        try:
            hdrs = {str(k).lower(): v for k, v in dict(headers or {}).items()}
        except Exception:
            hdrs = dict(headers or {})
        if "content-type" not in hdrs and "Content-Type" in (headers or {}):
            hdrs["content-type"] = headers["Content-Type"]  # type: ignore[index]
        return {"url": str(url), "headers": hdrs}

    def head_object(self, *, bucket: str, key: str) -> Dict[str, Any]:
        b = self._bucket(bucket)
        norm_key = key.lstrip("/")
        prefix = f"{bucket}/"
        if norm_key.startswith(prefix):
            norm_key = norm_key[len(prefix):]
        # Preferred: use client-provided stat when available (older clients)
        try:
            info = b.stat(norm_key)  # type: ignore[attr-defined]
        except AttributeError:
            info = None
        except Exception:
            info = None
        if isinstance(info, dict):
            # supabase-py variants report either top-level or nested `data`
            data = info.get("data") if "data" in info and isinstance(info.get("data"), dict) else info
            size = data.get("size")
            mime = data.get("mimetype") or data.get("content_type")
            return {"content_length": size, "content_type": mime}

        # Fallback: HEAD the signed download URL to infer metadata
        try:
            res = b.create_signed_url(norm_key, 60)  # returns dict with url/signed_url
            url = None
            if isinstance(res, dict):
                url = self._first_key(res, "url", "signed_url", "signedURL")
                data = res.get("data") if "data" in res else None
                if url is None and isinstance(data, dict):
                    url = self._first_key(data, "url", "signed_url", "signedURL")
            if not url:
                # Best-effort tuple/list shape
                try:
                    data = res[0] if isinstance(res, (list, tuple)) else None
                    if isinstance(data, dict):
                        url = self._first_key(data, "url", "signed_url", "signedURL")
                except Exception:
                    pass
            if not url:
                raise RuntimeError("failed_to_presign_download")
            import requests  # local import to avoid hard dep in tests
            # Apply a conservative timeout to prevent hangs under network issues.
            head = requests.head(self._normalize_signed_url_host(str(url)), timeout=5)
            ctype = head.headers.get("content-type") or head.headers.get("Content-Type")
            clen = head.headers.get("content-length") or head.headers.get("Content-Length")
            try:
                size = int(clen) if clen is not None else None
            except Exception:
                size = None
            return {"content_length": size, "content_type": ctype}
        except Exception:
            # Report unknowns to let callers decide on fallback behavior
            return {"content_length": None, "content_type": None}

    def delete_object(self, *, bucket: str, key: str) -> None:
        b = self._bucket(bucket)
        # Supabase Storage remove expects paths relative to the bucket
        norm_key = key.lstrip("/")
        prefix = f"{bucket}/"
        if norm_key.startswith(prefix):
            norm_key = norm_key[len(prefix):]
        b.remove([norm_key])

    def presign_download(self, *, bucket: str, key: str, expires_in: int, disposition: str) -> Dict[str, Any]:
        b = self._bucket(bucket)
        norm_key = key.lstrip("/")
        prefix = f"{bucket}/"
        if norm_key.startswith(prefix):
            norm_key = norm_key[len(prefix):]
        # Some clients accept an options dict to influence content-disposition via `download` param.
        # We provide a hint but servers may ignore it; our API consumes only the URL + expires.
        opts = {"download": None if disposition == "inline" else norm_key.split("/")[-1]}
        res = b.create_signed_url(norm_key, expires_in, opts)
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
        return {"url": self._normalize_signed_url_host(str(url)), "expires_at": expires_at}

    # --- Binary write support (used by Vision pipeline) ------------------------

    def put_object(self, *, bucket: str, key: str, body: bytes, content_type: str) -> None:
        """Upload a binary object to Supabase Storage.

        Behavior:
            - Normalizes the key by stripping a leading slash, if present.
            - Passes content-type via options to be compatible across client versions
              (supports both "content-type" and "contentType" keys).

        Raises:
            Propagates client exceptions. No return value on success.
        """
        b = self._bucket(bucket)
        # Normalize keys to avoid accidental absolute-like paths
        norm_key = key[1:] if key.startswith("/") else key
        # Some client versions expect file options with either kebab or camel case.
        opts = {"content-type": content_type, "contentType": content_type}
        # Supabase Storage `upload` can accept raw bytes for small objects.
        # We rely on the client to stream efficiently if needed.
        b.upload(norm_key, body, opts)

    # --- Local helpers ---------------------------------------------------------

    def _normalize_signed_url_host(self, url: str) -> str:
        """For local dev, rewrite signed URL host to SUPABASE_URL host.

        Why:
            Some local setups return signed URLs with container-internal hosts
            that are not resolvable from the test runner. Rewriting the host to
            the configured SUPABASE_URL keeps signatures valid (token is path‑
            bound) and makes direct PUT/GET calls succeed.

        Behavior:
            - Only rewrites when SUPABASE_URL is set and appears local
              (host is 127.0.0.1 or localhost), or when the explicit toggle
              SUPABASE_REWRITE_SIGNED_URL_HOST=true is set.
            - Scheme and port are taken from SUPABASE_URL; path/query/fragment
              are preserved from the original signed URL.
        """
        base = (os.getenv("SUPABASE_URL") or "").strip()
        if not base:
            return url
        try:
            src = _urlparse(url)
            dst = _urlparse(base)
            if not src.scheme or not src.netloc:
                return url
            # Only rewrite when explicitly enabled to avoid surprising unit tests.
            force = (os.getenv("SUPABASE_REWRITE_SIGNED_URL_HOST", "false").lower() == "true")
            if not force:
                return url
            # If hosts already match, keep as is.
            if (src.hostname, src.port, src.scheme) == (dst.hostname, dst.port, dst.scheme):
                # Also normalize path prefix for storage endpoints: some clients
                # return paths without the "/storage/v1" prefix. Insert it when
                # missing to target the storage API consistently.
                path = src.path or "/"
                if path.startswith("/object/") or path.startswith("/sign/"):
                    path = "/storage/v1" + path
                # Collapse accidental double slashes.
                while "//" in path:
                    path = path.replace("//", "/")
                return _urlunparse((src.scheme, src.netloc, path, src.params, src.query, src.fragment))
            # Rebuild URL with base host:port and scheme, preserve path/query
            netloc = dst.hostname or ""
            if dst.port and ((dst.scheme == "http" and dst.port != 80) or (dst.scheme == "https" and dst.port != 443)):
                netloc = f"{netloc}:{dst.port}"
            # Normalize path prefix for storage API
            path = src.path or "/"
            if path.startswith("/object/") or path.startswith("/sign/"):
                # Ensure "/storage/v1" prefix
                path = "/storage/v1" + path
            while "//" in path:
                path = path.replace("//", "/")
            rebuilt = _urlunparse((dst.scheme or src.scheme, netloc, path, src.params, src.query, src.fragment))
            return rebuilt
        except Exception:
            return url


__all__ = ["SupabaseStorageAdapter"]
