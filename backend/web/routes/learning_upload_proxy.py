"""Upload-proxy helpers for Learning storage uploads.

Why:
    The Learning upload proxy has security-sensitive helper logic for presign
    header encoding, header allowlisting, target-origin normalization, and the
    upstream PUT. Keeping these helpers outside the route module makes the route
    adapter easier to read while preserving the same endpoint contract.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx


def encode_proxy_headers(headers: Any) -> str | None:
    """Return a base64url-encoded JSON payload containing presign headers."""

    if not headers:
        return None
    try:
        mapping = dict(headers)
    except Exception:
        return None
    safe: dict[str, str] = {}
    for key, value in mapping.items():
        if key is None or value is None:
            continue
        k = str(key).strip()
        if not k:
            continue
        safe[k] = str(value)
    if not safe:
        return None
    raw = json.dumps(safe, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_proxy_headers(token: str | None) -> dict[str, str]:
    """Decode encoded presign headers, failing closed to an empty mapping."""

    if not token:
        return {}
    try:
        padded = token + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        parsed = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}
    safe: dict[str, str] = {}
    for key, value in parsed.items():
        if isinstance(key, str) and isinstance(value, str):
            safe[key] = value
    return safe


def filter_upload_proxy_headers(headers: dict[str, str]) -> dict[str, str]:
    """Return a safe allowlist of headers for the internal upload proxy."""

    allowed = {"content-type", "x-upsert"}
    out: dict[str, str] = {}
    for key, value in (headers or {}).items():
        lk = str(key).strip().lower()
        if not lk or lk not in allowed:
            continue
        out[str(key)] = str(value)
    return out


def normalized_parts(parsed: object) -> tuple[str, str, int | None]:
    """Return normalized `(scheme, host, port)` parts for URL validation."""

    scheme = (getattr(parsed, "scheme", "") or "").lower()
    host = (getattr(parsed, "hostname", "") or "").lower()
    port = getattr(parsed, "port", None)
    if port is None:
        if scheme == "https":
            port = 443
        elif scheme == "http":
            port = 80
    return scheme, host, port


async def async_forward_upload(
    *,
    url: str,
    payload: bytes,
    content_type: str,
    timeout: float,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Forward the upload bytes to the presigned Supabase Storage URL."""

    send_headers: dict[str, str] = {}
    if headers:
        for key, value in headers.items():
            if key is None or value is None:
                continue
            send_headers[str(key)] = str(value)
    if not any(str(k).lower() == "content-type" for k in send_headers):
        send_headers["Content-Type"] = content_type
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.put(url, content=payload, headers=send_headers)
