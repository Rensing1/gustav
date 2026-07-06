"""Storage validation helpers for Learning submissions."""

from __future__ import annotations

import importlib
import os
import sys as _sys
from pathlib import Path

from backend.storage.learning_policy import resolve_local_verify_root_from_env, verification_config_from_env
from backend.storage.verification import verify_storage_object_integrity
from backend.teaching.storage import NullStorageAdapter
from backend.web.routes import learning_downloads


def _learning_module():
    module = _sys.modules.get("backend.web.routes.learning")
    if module is None:  # pragma: no cover - defensive import fallback
        module = importlib.import_module("backend.web.routes.learning")
    return module


def _current_storage_adapter():
    return _learning_module()._current_storage_adapter()


def _current_environment() -> str:
    return str(_learning_module()._current_environment())


def _storage_bucket() -> str:
    return str(_learning_module()._storage_bucket())


def verify_storage_object(storage_key: str, sha256: str, size_bytes: int, mime_type: str) -> tuple[bool, str]:
    """Validate that a referenced storage object matches submission metadata."""

    config = verification_config_from_env()
    return verify_storage_object_integrity(
        adapter=_current_storage_adapter(),
        storage_key=storage_key,
        expected_sha256=sha256,
        expected_size=size_bytes,
        mime_type=mime_type,
        config=config,
    )


def load_local_storage_bytes_for_validation(*, root: str, storage_key: str, max_bytes: int) -> bytes | None:
    """Read a local file beneath STORAGE_VERIFY_ROOT with path containment checks."""

    if not root or not storage_key:
        return None
    try:
        base = Path(root).resolve()
        target = (base / storage_key).resolve()
        common = os.path.commonpath([str(base), str(target)])
    except Exception:
        return None
    if common != str(base) or (not target.exists()) or (not target.is_file()):
        return None
    try:
        size = int(target.stat().st_size)
    except Exception:
        return None
    if size <= 0 or size > int(max_bytes):
        return None
    try:
        return target.read_bytes()
    except Exception:
        return None


async def download_bytes_with_limit(*, url: str, max_bytes: int, headers: dict[str, str] | None = None) -> bytes | None:
    """Download bytes from a presigned URL with a hard cap and SSRF guards."""

    return await learning_downloads.download_bytes_with_limit(
        url=url,
        max_bytes=max_bytes,
        headers=headers,
        environment=_current_environment(),
    )


async def load_storage_bytes_for_validation(*, storage_key: str, max_bytes: int) -> bytes | None:
    """Fetch bytes for validation either from local verify root or via presigned download."""

    root = resolve_local_verify_root_from_env() or ""
    local = load_local_storage_bytes_for_validation(root=root, storage_key=storage_key, max_bytes=max_bytes)
    if local is not None:
        return local

    bucket = _storage_bucket()
    adapter = _current_storage_adapter()
    if not bucket or isinstance(adapter, NullStorageAdapter):
        return None
    try:
        presigned = adapter.presign_download(bucket=bucket, key=storage_key, expires_in=60, disposition="inline")
    except Exception:
        return None
    url = str((presigned or {}).get("url") or "").strip()
    headers = presigned.get("headers") if isinstance(presigned, dict) else None
    try:
        hdrs = {str(k): str(v) for k, v in dict(headers or {}).items() if k and v}
    except Exception:
        hdrs = None
    downloader = getattr(_learning_module(), "_download_bytes_with_limit", download_bytes_with_limit)
    return await downloader(url=url, max_bytes=max_bytes, headers=hdrs)
