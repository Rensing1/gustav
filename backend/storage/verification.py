"""
Helpers for verifying storage objects referenced by presigned uploads.

The learning ingestion flow reuses this to assert that the object uploaded to
Supabase (or the local stub) matches the metadata submitted by the client.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from hashlib import sha256 as _sha256
from pathlib import Path
from typing import Protocol

from teaching.storage import NullStorageAdapter, StorageAdapterProtocol  # type: ignore
from backend.storage.config import get_learning_max_upload_bytes

def _stream_hash_from_url(
    url: str,
    *,
    timeout: float = 15.0,
    max_bytes: int | None = None,
) -> tuple[bool, str | None, int | None, str]:
    """
    Download content from a URL and compute its SHA-256 in a streaming fashion.

    Returns (ok, hex_sha256 | None, size | None, reason).

    Notes:
        - Uses httpx if available; otherwise, returns a failure.
        - Enforces a hard maximum on downloaded bytes to avoid memory pressure.
          Limit is read from centralized config (LEARNING_MAX_UPLOAD_BYTES).
    """
    try:
        import httpx  # type: ignore
    except Exception:
        return (False, None, None, "http_client_unavailable")

    try:
        # Enforce host allowlist: only permit downloads from trusted storage hosts
        # Trust either the internal SUPABASE_URL host (Kong) or the browser-facing
        # SUPABASE_PUBLIC_URL host when a path-proxy is used (same-origin setups).
        from urllib.parse import urlparse

        supabase_base = (os.getenv("SUPABASE_URL") or "").strip()
        public_base = (os.getenv("SUPABASE_PUBLIC_URL") or "").strip()
        sup_host = urlparse(supabase_base).hostname or ""
        pub_host = urlparse(public_base).hostname or ""
        target = urlparse(url)
        tgt_host = target.hostname or ""
        allowed_hosts = {h for h in (sup_host, pub_host) if h}
        if not allowed_hosts or (tgt_host not in allowed_hosts):
            return (False, None, None, "untrusted_host")

        # Prefer internal gateway for server-side verification to avoid TLS trust
        # issues against the browser-facing host (e.g., local Caddy CA). If the
        # download URL uses the public host and an internal SUPABASE_URL exists,
        # rewrite scheme/host/port to the internal base while preserving path/query.
        if pub_host and sup_host and tgt_host == pub_host and supabase_base:
            tb = urlparse(url)
            ib = urlparse(supabase_base)
            if ib.scheme and ib.netloc:
                netloc = ib.netloc
                url = tb._replace(scheme=ib.scheme, netloc=netloc).geturl()

        # Resolve dynamic cap at call time to avoid drift with central config
        limit = int(max_bytes) if isinstance(max_bytes, int) and max_bytes > 0 else get_learning_max_upload_bytes()
        h = _sha256()
        total = 0
        # Do not follow redirects; unexpected redirects can escape the allowlisted host
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:  # type: ignore
            with client.stream("GET", url) as resp:  # type: ignore
                code = int(getattr(resp, "status_code", 500))
                if 300 <= code < 400:
                    return (False, None, None, "redirect_detected")
                if code >= 400:
                    return (False, None, None, "download_error")
                for chunk in resp.iter_bytes():  # type: ignore[attr-defined]
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > limit:
                        return (False, None, total, "size_exceeded")
                    h.update(chunk)
        return (True, h.hexdigest(), total, "ok")
    except Exception:
        return (False, None, None, "download_exception")


@dataclass(frozen=True, slots=True)
class VerificationConfig:
    """Declarative settings that drive integrity verification."""

    storage_bucket: str
    require_remote: bool = False
    local_verify_root: str | None = None
    retry_attempts: int = 3
    retry_sleep_seconds: float = 0.2


def verify_storage_object_integrity(
    *,
    adapter: StorageAdapterProtocol,
    storage_key: str,
    expected_sha256: str,
    expected_size: int | None,
    mime_type: str,
    config: VerificationConfig,
) -> tuple[bool, str]:
    """
    Verify a storage object by comparing size and SHA-256 hash.

    Returns tuple (ok, reason). When `config.require_remote` is False, the helper
    falls back to best-effort verification and reports "skipped" if the object
    cannot be found.
    """

    bucket = config.storage_bucket
    # Interpret `require_remote` as "verification is required", not strictly
    # "remote HEAD must succeed". In dev/test setups a local verify root may
    # be configured and should be authoritative when present.
    require = config.require_remote

    remote_checked = False
    last_reason = "missing_object"
    head_seen = False
    if bucket and not isinstance(adapter, NullStorageAdapter):
        attempts = config.retry_attempts if require else 1
        for attempt in range(max(1, attempts)):
            try:
                head = adapter.head_object(bucket=bucket, key=storage_key)
            except RuntimeError as exc:
                if str(exc) == "storage_adapter_not_configured":
                    last_reason = "storage_adapter_not_configured"
                    break
                last_reason = "head_error"
            except Exception:
                last_reason = "head_error"
            else:
                if head:
                    head_seen = True
                    length = head.get("content_length")
                    etag = head.get("etag") or head.get("ETag") or head.get("sha256") or head.get("content_sha256")
                    expected_size_int = None
                    actual_size = None
                    try:
                        expected_size_int = int(expected_size) if expected_size is not None else None
                    except Exception:
                        expected_size_int = None
                    if length is not None:
                        try:
                            actual_size = int(length)
                        except Exception:
                            actual_size = None
                    if expected_size_int is not None and actual_size is not None and expected_size_int != actual_size:
                        last_reason = "size_mismatch"
                    elif expected_sha256 and etag:
                        # Only accept a trusted SHA-256 header name; generic ETags are
                        # not reliable checksums in many backends (e.g., Supabase).
                        # Some providers put sha256 in custom headers (e.g., content_sha256).
                        # Treat unknown/opaque ETags as non-authoritative.
                        name = None
                        for k in ("sha256", "content_sha256"):
                            if k in head:
                                name = k
                                break
                        if name is not None:
                            normalized = str(head.get(name)).strip('"').lower()
                            if normalized != str(expected_sha256).lower():
                                last_reason = "hash_mismatch"
                            else:
                                return (True, "ok")
                        else:
                            last_reason = "hash_unavailable"
                    elif expected_size_int is not None and actual_size is not None:
                        return (True, "ok")
                    else:
                        last_reason = "unknown_size"
                else:
                    last_reason = "missing_object"

            if attempt < attempts - 1:
                time.sleep(config.retry_sleep_seconds)
        remote_checked = True

    # If strict verification is required and we saw a HEAD but no trustworthy
    # hash header, attempt a secure, bounded download to compute SHA-256.
    if require and head_seen and expected_sha256:
        try:
            dl = adapter.presign_download(bucket=bucket, key=storage_key, expires_in=60, disposition="inline")
            url = (dl or {}).get("url")
        except Exception:
            url = None
        if isinstance(url, str) and url:
            ok, actual_sha, actual_size, reason = _stream_hash_from_url(
                url,
                timeout=15.0,
                max_bytes=get_learning_max_upload_bytes(),
            )
            if ok and isinstance(actual_sha, str):
                # If expected size is known, enforce it too
                try:
                    expected_size_int2 = int(expected_size) if expected_size is not None else None
                except Exception:
                    expected_size_int2 = None
                if expected_size_int2 is not None and isinstance(actual_size, int) and actual_size != expected_size_int2:
                    return (False, "size_mismatch")
                if actual_sha.lower() == str(expected_sha256).lower():
                    return (True, "ok")
                else:
                    return (False, "hash_mismatch")
            else:
                # Preserve the more specific earlier reason when download failed
                last_reason = last_reason or reason or "download_failed"

    root = (config.local_verify_root or "").strip()
    if not root:
        # No local root available; if verification is required and remote
        # verification didn't succeed, propagate the remote failure reason.
        return ((not require), "skipped" if not require else last_reason)
    if not storage_key or not expected_sha256 or expected_size is None:
        return (False, "missing_fields")
    base = Path(root).resolve()
    target = (base / storage_key).resolve()
    try:
        # Defense-in-depth: ensure uploads stay within the configured root.
        common = os.path.commonpath([str(base), str(target)])
    except Exception:
        return (not require, "path_error" if require else "skipped")
    if common != str(base):
        return (not require, "path_escape" if require else "skipped")
    if not target.exists() or not target.is_file():
        return (not require, "missing_file" if require else "skipped")
    actual_size = target.stat().st_size
    if expected_size is None or int(actual_size) != int(expected_size):
        return (not require, "size_mismatch" if require else "skipped")
    h = _sha256()
    with target.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    actual_hash = h.hexdigest()
    if actual_hash.lower() != str(expected_sha256).lower():
        return (not require, "hash_mismatch" if require else "skipped")
    return (True, "ok")
