"""
Tests for authentication-enforcing middleware.

Requirements:
- HTML requests without session → 302 to /auth/login
- JSON/API requests without session → 401 JSON
- HTMX requests without session → 401 + HX-Redirect header
- Allowlist: /auth/*, /health, /static/* are not redirected
"""

import pytest
import httpx
from httpx import ASGITransport
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


@pytest.mark.anyio
async def test_html_request_without_session_redirects_to_login():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/", headers={"Accept": "text/html"}, follow_redirects=False)
    assert r.status_code in (301, 302, 303)
    assert r.headers.get("location") == "/auth/login"


@pytest.mark.anyio
async def test_json_request_without_session_returns_401():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/api/me", headers={"Accept": "application/json"})
    assert r.status_code == 401
    assert r.headers.get("Cache-Control") == "no-store"


@pytest.mark.anyio
async def test_htmx_request_without_session_returns_401_with_hx_redirect():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/dashboard", headers={"HX-Request": "true"}, follow_redirects=False)
    assert r.status_code == 401
    assert r.headers.get("HX-Redirect") == "/auth/login"


@pytest.mark.anyio
async def test_allowlist_paths_not_redirected():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r_auth = await client.get("/auth/login", follow_redirects=False)
        r_health = await client.get("/health")
        # Static path may 404 if file missing, but must not be a redirect to /auth/login
        r_static = await client.get("/static/does-not-exist.css", follow_redirects=False)

    assert r_auth.status_code in (200, 302, 303)
    assert r_health.status_code == 200
    assert r_static.status_code != 302 or r_static.headers.get("location") != "/auth/login"


@pytest.mark.anyio
async def test_favicon_is_allowlisted():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r_favicon = await client.get("/favicon.ico", follow_redirects=False)
    # It may 404, but must not redirect to login
    assert r_favicon.status_code != 302 or r_favicon.headers.get("location") != "/auth/login"
