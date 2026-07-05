"""Upload configuration helpers for Learning routes.

Why:
    Learning upload flows use several environment-controlled switches. Keeping
    their parsing and clamping in a small module makes route code easier to read
    and keeps production/local behavior consistent.
"""

from __future__ import annotations

import os


def upload_intent_ttl_seconds() -> int:
    """Return the short-lived upload-intent TTL, clamped to 1 minute..24 hours."""

    raw = (os.getenv("LEARNING_UPLOAD_INTENT_TTL_SECONDS") or "").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 600
    return max(60, min(value, 24 * 60 * 60))


def dev_upload_stub_enabled() -> bool:
    """Return whether the local dev upload stub is explicitly enabled."""

    return (os.getenv("ENABLE_DEV_UPLOAD_STUB", "false") or "").strip().lower() == "true"


def upload_proxy_enabled() -> bool:
    """Return whether upload intents should use the same-origin upload proxy."""

    return (os.getenv("ENABLE_STORAGE_UPLOAD_PROXY", "false") or "").strip().lower() == "true"


def upload_proxy_timeout_seconds() -> float:
    """Return the upstream upload-proxy timeout, clamped to 5..120 seconds."""

    raw = (os.getenv("LEARNING_UPLOAD_PROXY_TIMEOUT_SECONDS") or "").strip()
    try:
        value = float(raw)
    except ValueError:
        value = 30.0
    return max(5.0, min(value, 120.0))
