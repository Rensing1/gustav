"""
Shared redirect helpers for the GUSTAV web layer.

Why:
    Several endpoints accept a "return-to" path (query parameter `redirect`).
    This must never become an open redirect (external URL) or a traversal
    vector. We therefore only allow absolute in-app paths and reject:
      - URLs with scheme/host
      - query strings / fragments
      - double slashes ("//")
      - traversal segments ("..")

Contract:
    Keep `INAPP_PATH_PATTERN` in sync with `api/openapi.yml` for all `redirect`
    query parameters.
"""

from __future__ import annotations

import re

MAX_INAPP_REDIRECT_LEN = 256
INAPP_PATH_PATTERN = re.compile(r"^(?!.*//)(?!.*\.\.)/[A-Za-z0-9._\-/]*$")


def safe_inapp_path(value: str | None) -> str | None:
    """Return a safe absolute in-app path or None.

    Examples (accepted):
        "/", "/courses", "/courses/1", "/courses/list_all"
    Examples (rejected):
        "courses" (not absolute), "https://evil.com", "/a?b", "/a#b", "/..", "//"
    """
    if not value or not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if len(candidate) > MAX_INAPP_REDIRECT_LEN:
        return None
    return candidate if INAPP_PATH_PATTERN.fullmatch(candidate) else None


def is_inapp_path(value: str) -> bool:
    """Return True if value is a safe absolute in-app path."""
    return safe_inapp_path(value) is not None

