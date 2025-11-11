"""
Supabase Storage bootstrap helpers.

Intent:
    Ensure required storage buckets exist on startup (dev/stage friendly).

Security & Safety:
    - Controlled by `AUTO_CREATE_STORAGE_BUCKETS=true` env flag.
    - Requires server-side `SUPABASE_SERVICE_ROLE_KEY`.
    - Idempotent: lists buckets first, creates only missing ones.

Usage:
    Call `ensure_buckets_from_env()` after wiring the storage adapter.
"""
from __future__ import annotations

import os
from typing import Iterable
import inspect

import requests
import logging

_log = logging.getLogger("gustav.storage")


def _env_flag(name: str, default: str = "false") -> bool:
    return (os.getenv(name, default) or "").strip().lower() == "true"


def _supports_timeout(func) -> bool:
    """Return True if callable signature supports a 'timeout' kw or **kwargs.

    This guards tests that monkeypatch `bootstrap.requests` with simple callables
    not accepting a `timeout` keyword argument, while keeping timeouts enabled
    for real HTTP clients.
    """
    try:
        sig = inspect.signature(func)
        if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            return True
        return "timeout" in sig.parameters
    except Exception:
        return False


def _list_buckets(base_url: str, key: str) -> list[dict]:
    url = f"{base_url.rstrip('/')}/storage/v1/bucket"
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    try:
        get = getattr(requests, "get")
        kwargs = {"headers": headers}
        if _supports_timeout(get):
            kwargs["timeout"] = (3, 10)
        resp = get(url, **kwargs)
        try:
            _log.debug("GET /storage/v1/bucket status=%s", getattr(resp, "status_code", "?"))
        except Exception:
            pass
        try:
            data = resp.json() if hasattr(resp, "json") else []
        except Exception:
            data = []
        return data if isinstance(data, list) else []
    except Exception as exc:
        try:
            _log.warning("list buckets failed: error=%s", type(exc).__name__)
        except Exception:
            pass
        return []


def _create_bucket(base_url: str, key: str, name: str, public: bool = False) -> bool:
    url = f"{base_url.rstrip('/')}/storage/v1/bucket"
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"name": name, "public": public}
    try:
        post = getattr(requests, "post")
        kwargs = {"headers": headers, "json": payload}
        if _supports_timeout(post):
            kwargs["timeout"] = (3, 10)
        resp = post(url, **kwargs)
        status = getattr(resp, "status_code", 500)
        # Log outcome for diagnostics (e.g., 409 conflict / 403 forbidden / 503 unavailable)
        try:
            body_text = getattr(resp, "text", "")
        except Exception:
            body_text = ""
        if status >= 300:
            _log.warning("create bucket '%s' failed: status=%s body=%s", name, status, body_text)
        else:
            _log.debug("POST /storage/v1/bucket status=%s created='%s'", status, name)
        return status < 300
    except Exception as exc:
        try:
            _log.warning("create bucket '%s' failed: error=%s", name, type(exc).__name__)
        except Exception:
            pass
        return False


def ensure_buckets(base_url: str, key: str, buckets: Iterable[str]) -> bool:
    """Ensure each bucket in `buckets` exists; create if missing.

    Why:
        Local/dev environments should work without manual Storage setup. This helper
        provisions missing buckets via Supabase's REST API.

    Parameters:
        base_url: Supabase API base (e.g., http://host.docker.internal:54321)
        key: Service role JWT for server-side administration
        buckets: Iterable of bucket names to ensure exist (private by default)

    Behavior:
        - Lists existing buckets, creates only missing ones (idempotent).
        - Logs non-2xx responses for visibility (e.g., 409/403/503).
        - Performs a best-effort verification via a follow-up list and warns if
          a requested bucket is still missing.

    Permissions:
        Caller must supply a valid service-role key; regular anon keys will not
        be able to create buckets and will yield 401/403.

    Returns:
        True (work attempted). Warnings in logs indicate problems to investigate.
    """
    existing = _list_buckets(base_url, key)
    names = {str(it.get("name") or it.get("id") or "") for it in existing}
    did = False
    for name in set(buckets):
        if not name:
            continue
        if name in names:
            continue
        _create_bucket(base_url, key, name, public=False)
        did = True
    # Verify existence after creation attempts and log if still missing.
    try:
        final = _list_buckets(base_url, key)
        final_names = {str(it.get("name") or it.get("id") or "") for it in final}
        for name in set(buckets):
            if name and name not in final_names:
                _log.warning("bucket '%s' still missing after create attempt", name)
    except Exception:
        # Best-effort verification; avoid raising during dev bootstrap.
        pass
    return True


def ensure_buckets_from_env() -> bool:
    """Read env and ensure buckets when AUTO_CREATE_STORAGE_BUCKETS=true.

    Why:
        Developer ergonomics: reduce friction after resets by auto-provisioning
        required buckets at app or worker startup when explicitly enabled.

    Env:
        - AUTO_CREATE_STORAGE_BUCKETS=true (opt-in safety)
        - SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (server-side credentials)
        - SUPABASE_STORAGE_BUCKET (default: materials)
        - LEARNING_STORAGE_BUCKET (default: submissions)

    Behavior:
        - No-ops when AUTO_CREATE_STORAGE_BUCKETS is not exactly 'true'.
        - Returns False when mandatory env is missing; otherwise delegates to
          ensure_buckets() and returns True.
        - Logs detailed diagnostics (status codes) for troubleshooting.

    Permissions:
        Requires service-role key; only to be called in trusted server context
        (never from client code).
    """
    if not _env_flag("AUTO_CREATE_STORAGE_BUCKETS"):
        return False
    _log.warning(
        "AUTO_CREATE_STORAGE_BUCKETS=true detected (dev/test convenience only). Disable this flag in prod/stage environments."
    )
    base = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not base or not key:
        return False
    teaching_bucket = (os.getenv("SUPABASE_STORAGE_BUCKET") or "materials").strip()
    learning_bucket = (os.getenv("LEARNING_STORAGE_BUCKET") or "submissions").strip()
    return ensure_buckets(base, key, [teaching_bucket, learning_bucket])


__all__ = ["ensure_buckets_from_env", "ensure_buckets"]
