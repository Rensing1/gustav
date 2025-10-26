"""
Global Security Headers – middleware coverage

Verifiziert, dass HTML- und JSON-Antworten die erwarteten Security-Header
enthalten (CSP, XFO, XCTO, Referrer-Policy, Permissions-Policy) und dass
HSTS nur in PROD aktiv ist.
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
from identity_access.stores import SessionStore


pytestmark = pytest.mark.anyio("asyncio")


def _assert_base_headers(hdrs: dict[str, str]) -> None:
    assert "Content-Security-Policy" in hdrs
    assert "X-Frame-Options" in hdrs
    assert "X-Content-Type-Options" in hdrs
    assert "Referrer-Policy" in hdrs
    assert "Permissions-Policy" in hdrs


@pytest.mark.anyio
async def test_html_route_includes_security_headers():
    # Arrange: ensure in-memory sessions and authenticated user
    if not isinstance(main.SESSION_STORE, SessionStore):  # pragma: no cover
        main.SESSION_STORE = SessionStore()
    sess = main.SESSION_STORE.create(sub="t-sec-1", name="Lehrkraft", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://app.localhost:8100") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r = await c.get("/")

    assert r.status_code == 200
    _assert_base_headers(r.headers)


@pytest.mark.anyio
async def test_api_route_includes_security_headers_and_hsts_only_in_prod(monkeypatch: pytest.MonkeyPatch):
    # Non-prod: HSTS absent
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://app.localhost:8100") as c:
        r = await c.get("/health")
    assert r.status_code == 200
    _assert_base_headers(r.headers)
    assert "Strict-Transport-Security" not in r.headers

    # Prod: HSTS present
    main.SETTINGS.override_environment("prod")
    try:
        async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://app.localhost:8100") as c:
            r2 = await c.get("/health")
        assert r2.status_code == 200
        _assert_base_headers(r2.headers)
        assert "Strict-Transport-Security" in r2.headers
    finally:
        main.SETTINGS.override_environment(None)

