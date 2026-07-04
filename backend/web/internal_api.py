"""Helpers for SSR-internal API hops through ASGITransport."""

from __future__ import annotations

import os
from typing import Any

import httpx
from httpx import ASGITransport


def resolve_internal_base(env_var: str) -> tuple[str, str]:
    """Resolve base URL and Origin for one SSR-internal API context.

    Order of precedence:
    1. Context-specific override, for example `TEACHING_INTERNAL_BASE_URL`.
    2. Shared `APP_INTERNAL_BASE_URL`.
    3. `http://local` for in-process ASGITransport loopback.
    """

    preferred = (os.getenv(env_var, "") or "").strip()
    shared = (os.getenv("APP_INTERNAL_BASE_URL", "") or "").strip()
    base = preferred or shared or "http://local"
    origin = base.rstrip("/") or "http://local"
    return base, origin


def learning_internal_base() -> tuple[str, str]:
    """Return the internal base URL and Origin for learning SSR calls."""

    return resolve_internal_base("LEARNING_INTERNAL_BASE_URL")


def teaching_internal_base() -> tuple[str, str]:
    """Return the internal base URL and Origin for teaching SSR calls."""

    return resolve_internal_base("TEACHING_INTERNAL_BASE_URL")


def internal_api_client(app: Any) -> httpx.AsyncClient:
    """Create an ASGI client with a CSRF-compatible Origin header."""

    base, origin = teaching_internal_base()
    return httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url=base,
        headers={"Origin": origin},
    )
