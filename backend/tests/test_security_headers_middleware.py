"""
Global Security Headers – middleware coverage

Verifiziert, dass HTML- und JSON-Antworten die erwarteten Security-Header
enthalten (CSP, XFO, XCTO, Referrer-Policy, Permissions-Policy) und dass
HSTS immer aktiv ist (dev = prod).
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest
import httpx
from httpx import ASGITransport


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore
from runtime_auth_helpers import install_session_store


pytestmark = pytest.mark.anyio("asyncio")


def _assert_base_headers(hdrs: dict[str, str]) -> None:
    assert "Content-Security-Policy" in hdrs
    assert "X-Frame-Options" in hdrs
    assert "X-Content-Type-Options" in hdrs
    assert "Referrer-Policy" in hdrs
    assert "Permissions-Policy" in hdrs


@pytest.mark.anyio
async def test_html_route_includes_security_headers(monkeypatch: pytest.MonkeyPatch):
    # Arrange: ensure in-memory sessions and authenticated user
    store = install_session_store(monkeypatch, main)
    sess = store.create(sub="t-sec-1", name="Lehrkraft", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://app.localhost:8100") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r = await c.get("/")

    assert r.status_code == 200
    _assert_base_headers(r.headers)


@pytest.mark.anyio
async def test_api_route_includes_security_headers_and_hsts_always(monkeypatch: pytest.MonkeyPatch):
    # Non-prod: HSTS present
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://app.localhost:8100") as c:
        r = await c.get("/health")
    assert r.status_code == 200
    _assert_base_headers(r.headers)
    assert "Strict-Transport-Security" in r.headers

    # Prod: HSTS also present
    main.RUNTIME.settings.override_environment("prod")
    try:
        async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://app.localhost:8100") as c:
            r2 = await c.get("/health")
        assert r2.status_code == 200
        _assert_base_headers(r2.headers)
        assert "Strict-Transport-Security" in r2.headers
    finally:
        main.RUNTIME.settings.override_environment(None)
