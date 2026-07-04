"""App-session TTL and cookie helpers for the FastAPI adapter."""

from __future__ import annotations

import logging
import os

from fastapi import Response

from backend.web.auth_utils import cookie_opts


SESSION_COOKIE_NAME = "gustav_session"
logger = logging.getLogger("gustav.identity_access")


def app_session_ttl_seconds() -> int:
    """Return the bounded TTL for GUSTAV's app-level session.

    Why:
        GUSTAV keeps an application session in addition to the Keycloak SSO
        session. The value must be long enough for classroom workflows while
        still being bounded for security.

    Permissions:
        This helper only reads configuration. It does not authenticate a user
        and must be combined with trusted session-store operations.
    """

    raw = (os.getenv("APP_SESSION_TTL_SECONDS") or "").strip()
    default_seconds = 24 * 60 * 60
    try:
        value = int(raw) if raw else default_seconds
    except ValueError:
        logger.warning("Invalid APP_SESSION_TTL_SECONDS; falling back to default")
        value = default_seconds
    return max(15 * 60, min(value, 7 * 24 * 60 * 60))


def session_cookie_options(environment: str) -> dict[str, object]:
    """Return the environment-specific cookie security flags."""

    return cookie_opts(environment)


def set_session_cookie(
    response: Response,
    value: str,
    *,
    environment: str,
    max_age: int | None = None,
) -> None:
    """Write the opaque GUSTAV app-session cookie.

    The cookie contains only the session id; all user data remains server-side
    in the configured session store.
    """

    opts = session_cookie_options(environment)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=value,
        httponly=True,
        secure=bool(opts["secure"]),
        samesite=str(opts["samesite"]),
        path="/",
        max_age=max_age if max_age is not None else None,
    )
