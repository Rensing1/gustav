"""
Auth contract tests (RED phase)

These tests assert the behavior defined in api/openapi.yml for the minimal
authentication slice (login, callback, logout, me, forgot). External IdP
interactions (Keycloak) are not performed here; we only assert HTTP contracts.
"""

import pytest
import anyio
import httpx
from httpx import ASGITransport
from pathlib import Path
import sys

# Import auth-only app factory to keep tests lean
REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))
from main import create_app_auth_only  # type: ignore

# Force anyio to use asyncio backend only to avoid trio parametrization
pytestmark = pytest.mark.anyio("asyncio")


def is_redirect(status: int) -> bool:
    return status in (302, 303, 307, 308)


@pytest.mark.anyio
async def test_login_redirect():
    # Given: not authenticated (no cookie)
    # When: GET /auth/login
    app = create_app_auth_only()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/auth/login", follow_redirects=False)
    # Then: 302 Redirect to Keycloak (contract)
    assert resp.status_code == 302
    assert "location" in resp.headers


@pytest.mark.anyio
async def test_forgot_redirect():
    app = create_app_auth_only()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/auth/forgot", follow_redirects=False)
    assert resp.status_code == 302
    assert "location" in resp.headers


@pytest.mark.anyio
@pytest.mark.parametrize(
    "code,state",
    [
        ("valid-code", "opaque-state"),
    ],
)
async def test_callback_success_redirects_and_sets_cookie(code: str, state: str):
    # When: GET /auth/callback with a (mock) valid code and state
    app = create_app_auth_only()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/auth/callback?code={code}&state={state}", follow_redirects=False)
    # Then: 302 + both headers present (strict per contract)
    assert resp.status_code == 302
    set_cookie = resp.headers.get("set-cookie", "")
    assert "gustav_session=" in set_cookie
    assert "location" in resp.headers


@pytest.mark.anyio
@pytest.mark.parametrize(
    "code,state",
    [
        ("", "opaque"),
        ("invalid", ""),
        ("invalid", "invalid"),
    ],
)
async def test_callback_invalid_returns_400(code: str, state: str):
    app = create_app_auth_only()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/auth/callback?code={code}&state={state}")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_me_unauthenticated_returns_401():
    app = create_app_auth_only()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/me")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_logout_requires_authentication():
    app = create_app_auth_only()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Without cookie, the security scheme should require auth
        resp = await client.post("/auth/logout")
    assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_logout_clears_cookie():
    # With a (fake) session cookie, logout should clear it
    cookies = {"gustav_session": "fake-session"}
    app = create_app_auth_only()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("gustav_session", "fake-session")
        resp = await client.post("/auth/logout", follow_redirects=False)
    assert resp.status_code == 204
    # Contract: server clears the session cookie
    set_cookie = resp.headers.get("set-cookie", "")
    assert "gustav_session=" in set_cookie
    assert "Max-Age=0" in set_cookie or "max-age=0" in set_cookie


@pytest.mark.anyio
async def test_me_authenticated_returns_200_and_shape():
    # With a (fake) session cookie, /api/me should return session shape
    cookies = {"gustav_session": "fake-session"}
    app = create_app_auth_only()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("gustav_session", "fake-session")
        resp = await client.get("/api/me")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, dict)
    assert "email" in body and isinstance(body["email"], str)
    assert "roles" in body and isinstance(body["roles"], list)


def test_openapi_contains_auth_paths():
    # Sanity check that contract includes expected paths
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2]
    yml = (root / "api" / "openapi.yml").read_text(encoding="utf-8")
    for p in [
        "/auth/login",
        "/auth/callback",
        "/auth/logout",
        "/auth/forgot",
        "/api/me",
    ]:
        assert p in yml
