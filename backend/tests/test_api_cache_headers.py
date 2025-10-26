"""
Cache-Control and CSP hardening tests.

Ensures sensitive API responses are not cached and production CSP avoids
"unsafe-inline" to reduce XSS surface.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest
import httpx
from httpx import ASGITransport


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore
from identity_access.stores import SessionStore


pytestmark = pytest.mark.anyio("asyncio")


# Ensure in-memory session store for tests
if not isinstance(main.SESSION_STORE, SessionStore):  # pragma: no cover - defensive
    main.SESSION_STORE = SessionStore()


@pytest.mark.anyio
async def test_courses_list_includes_private_no_store_cache_header():
    sess = main.SESSION_STORE.create(sub="t-cache-1", name="Teacher", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r = await c.get("/api/teaching/courses", params={"limit": 1, "offset": 0})

    assert r.status_code == 200
    cc = r.headers.get("Cache-Control", "")
    assert "private" in cc and "no-store" in cc


@pytest.mark.anyio
async def test_prod_csp_omits_unsafe_inline_and_sets_hsts():
    # Switch to prod and assert CSP does not include 'unsafe-inline'
    main.SETTINGS.override_environment("prod")
    try:
        async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
            r = await c.get("/health")
        assert r.status_code == 200
        csp = r.headers.get("Content-Security-Policy", "")
        assert csp and "unsafe-inline" not in csp
        # HSTS should be set in prod (covered elsewhere, re-assert here for completeness)
        assert "Strict-Transport-Security" in r.headers
    finally:
        main.SETTINGS.override_environment(None)

