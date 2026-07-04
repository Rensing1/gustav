"""Session-bound SSR CSRF token helpers."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time

from backend.web.auth_session import app_session_ttl_seconds


_CSRF_BY_SESSION: dict[str, str] = {}
_DEV_CSRF_SIGNING_SECRET = secrets.token_bytes(32)


def csrf_ttl_seconds() -> int:
    """Return the bounded SSR CSRF token TTL.

    Why:
        Legacy SSR forms need a synchronizer token that survives normal
        classroom workflows but cannot become an unbounded bearer secret.

    Permissions:
        This helper only reads configuration. Route handlers still need their
        normal authentication and authorization checks.
    """

    raw = (os.getenv("APP_CSRF_TTL_SECONDS") or "").strip()
    default_seconds = app_session_ttl_seconds()
    try:
        value = int(raw) if raw else default_seconds
    except ValueError:
        value = default_seconds
    return max(60, min(value, 7 * 24 * 60 * 60))


def csrf_signing_secret() -> bytes:
    """Resolve the stable signing secret for session-bound CSRF tokens."""

    explicit = (os.getenv("APP_CSRF_TOKEN_SECRET") or "").strip()
    if explicit:
        return explicit.encode("utf-8")
    env = (os.getenv("GUSTAV_ENV", "dev") or "dev").strip().lower()
    if env in {"prod", "production", "stage", "staging"}:
        raise RuntimeError("APP_CSRF_TOKEN_SECRET is required in production/staging")
    shared = (os.getenv("H5P_REVIEW_TOKEN_SECRET") or "").strip()
    if shared:
        return shared.encode("utf-8")
    return _DEV_CSRF_SIGNING_SECRET


def sign_csrf_token(*, session_id: str, expires_at: int) -> str:
    """Create the HMAC signature for a session-bound CSRF token."""

    payload = f"{session_id}.{expires_at}".encode("utf-8")
    return hmac.new(csrf_signing_secret(), payload, hashlib.sha256).hexdigest()


def get_or_create_csrf_token(session_id: str) -> str:
    """Return a signed CSRF token for one server-side app session."""

    if not session_id:
        return ""
    expires_at = int(time.time()) + csrf_ttl_seconds()
    sig = sign_csrf_token(session_id=session_id, expires_at=expires_at)
    return f"v1.{expires_at}.{sig}"


def validate_csrf(session_id: str | None, form_value: str | None) -> bool:
    """Validate a signed or legacy rollout CSRF token for one session."""

    if not session_id or not form_value:
        return False
    token = str(form_value)
    parts = token.split(".")
    if len(parts) == 3 and parts[0] == "v1":
        try:
            expires_at = int(parts[1])
        except (TypeError, ValueError):
            return False
        if expires_at < int(time.time()):
            return False
        expected_sig = sign_csrf_token(session_id=session_id, expires_at=expires_at)
        return hmac.compare_digest(expected_sig, parts[2])
    expected = _CSRF_BY_SESSION.get(session_id)
    if not expected:
        return False
    return hmac.compare_digest(expected, token)
