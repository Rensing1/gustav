"""
Auth endpoints Cache-Control hardening.

Validates that all authentication-related endpoints include
"Cache-Control: private, no-store" to prevent sensitive responses from being
cached by shared proxies or the browser's back-forward cache inappropriately.

TDD (Red): These tests guide adding headers to /auth/login, /auth/callback,
/auth/logout, and /auth/logout/success.
"""

from __future__ import annotations

import importlib

import pytest
import httpx
from httpx import ASGITransport


pytestmark = pytest.mark.anyio("asyncio")


main = importlib.import_module("backend.web.main")


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://app.localhost:8100")


@pytest.mark.anyio
async def test_auth_login_has_private_no_store_cache_header():
    async with (await _client()) as c:
        r = await c.get("/auth/login")
    assert r.status_code == 302
    cc = r.headers.get("Cache-Control", "")
    assert cc == "private, no-store"


@pytest.mark.anyio
async def test_auth_callback_400_has_private_no_store_cache_header():
    # Missing code/state → 400
    async with (await _client()) as c:
        r = await c.get("/auth/callback")
    assert r.status_code == 400
    cc = r.headers.get("Cache-Control", "")
    assert cc == "private, no-store"


@pytest.mark.anyio
async def test_auth_logout_has_private_no_store_cache_header():
    async with (await _client()) as c:
        r = await c.get("/auth/logout")
    assert r.status_code == 302
    cc = r.headers.get("Cache-Control", "")
    assert cc == "private, no-store"


@pytest.mark.anyio
async def test_auth_logout_success_has_private_no_store_cache_header():
    async with (await _client()) as c:
        r = await c.get("/auth/logout/success")
    assert r.status_code == 200
    cc = r.headers.get("Cache-Control", "")
    assert cc == "private, no-store"
