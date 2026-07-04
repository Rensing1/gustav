"""Security header policy helpers for the web adapter."""

from __future__ import annotations

from collections.abc import Callable
import os
from urllib.parse import urlparse

from fastapi import FastAPI, Request


def _public_origin(raw_url: str | None) -> str | None:
    """Return the scheme and host part of a browser-facing service URL."""

    value = (raw_url or "").strip()
    if not value:
        return None
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def build_security_header_defaults(
    *,
    environment: str,
    supabase_public_url: str | None = None,
) -> dict[str, str]:
    """Build default defensive response headers.

    Why:
        The FastAPI middleware should only apply headers. The policy itself is
        pure enough to test directly, including the browser-facing Supabase
        origin used by uploads.
    """

    public_url = supabase_public_url
    if public_url is None:
        public_url = os.getenv("SUPABASE_PUBLIC_URL")

    connect_sources = ["'self'"]
    public_origin = _public_origin(public_url)
    if public_origin and public_origin not in connect_sources:
        connect_sources.append(public_origin)

    csp = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; media-src 'self' data:; font-src 'self' data:; "
        f"connect-src {' '.join(connect_sources)};"
    )

    headers = {
        "Content-Security-Policy": csp,
        "X-Frame-Options": "SAMEORIGIN",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    }
    if environment == "prod":
        headers["Cross-Origin-Opener-Policy"] = "same-origin"
    return headers


def install_security_headers_middleware(
    app: FastAPI,
    *,
    environment_provider: Callable[[], str],
) -> None:
    """Install the defensive security-header middleware on a FastAPI app.

    The provider is called per request so tests and runtime settings can change
    the environment without rebuilding the app.
    """

    @app.middleware("http")
    async def _security_headers(request: Request, call_next):
        response = await call_next(request)
        headers = build_security_header_defaults(environment=environment_provider())
        for name, value in headers.items():
            response.headers.setdefault(name, value)
        return response
