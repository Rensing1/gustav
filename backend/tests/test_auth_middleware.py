"""
Tests for authentication-enforcing middleware.

Requirements:
- HTML requests without session → 302 to /auth/login with return-to
- JSON/API requests without session → 401 JSON
- HTMX requests without session → 401 + HX-Redirect header (with return-to)
- Allowlist: /auth/*, /health, /static/* are not redirected
"""

import pytest
import httpx
from httpx import ASGITransport
from urllib.parse import urlparse, parse_qs
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
    loc = r.headers.get("location", "")
    p = urlparse(loc)
    assert p.path == "/auth/login"
    qs = parse_qs(p.query)
    assert qs.get("redirect") == ["/"]


@pytest.mark.anyio
async def test_json_request_without_session_returns_401():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/api/me", headers={"Accept": "application/json"})
    assert r.status_code == 401
    assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_htmx_request_without_session_returns_401_with_hx_redirect():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/dashboard", headers={"HX-Request": "true"}, follow_redirects=False)
    assert r.status_code == 401
    hx = r.headers.get("HX-Redirect", "")
    p = urlparse(hx)
    assert p.path == "/auth/login"
    qs = parse_qs(p.query)
    assert qs.get("redirect") == ["/dashboard"]


@pytest.mark.anyio
async def test_htmx_unauthenticated_prefers_hx_current_url_for_return_to():
    """HTMX posts (e.g., /submit) should redirect back to the browser page, not the endpoint path."""
    headers = {
        "HX-Request": "true",
        # HTMX sends the full browser URL; the middleware must only use the path part.
        "HX-Current-URL": "https://app.localhost/learning/courses/c1/units/u1",
    }
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.post("/learning/courses/c1/tasks/t1/submit", headers=headers, follow_redirects=False)
    assert r.status_code == 401
    hx = r.headers.get("HX-Redirect", "")
    p = urlparse(hx)
    assert p.path == "/auth/login"
    qs = parse_qs(p.query)
    assert qs.get("redirect") == ["/learning/courses/c1/units/u1"]


@pytest.mark.anyio
async def test_allowlist_paths_not_redirected():
    # StaticFiles responses can be streaming; avoid exercising them via ASGITransport
    # here and instead assert the middleware's allowlist predicate directly.
    assert main._is_public_path("/static/css/gustav.css")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r_auth = await client.get("/auth/login", follow_redirects=False)
        r_health = await client.get("/health")

    assert r_auth.status_code in (200, 302, 303)
    assert r_health.status_code == 200


@pytest.mark.anyio
async def test_favicon_is_allowlisted():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r_favicon = await client.get("/favicon.ico", follow_redirects=False)
    # It may 404, but must not redirect to login
    assert r_favicon.status_code != 302 or r_favicon.headers.get("location") != "/auth/login"
