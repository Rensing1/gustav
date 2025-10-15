"""
Auth contract tests (RED phase)

These tests assert the behavior defined in api/openapi.yml for the minimal
authentication slice (login, callback, logout, me, forgot). External IdP
interactions (Keycloak) are not performed here; we only assert HTTP contracts.
"""

from typing import Iterable

import pytest
from fastapi.testclient import TestClient


def is_redirect(status: int) -> bool:
    return status in (302, 303, 307, 308)


def test_login_redirect(client: TestClient):
    # Given: not authenticated (no cookie)
    # When: GET /auth/login
    resp = client.get("/auth/login", allow_redirects=False)
    # Then: 302 Redirect to Keycloak (contract)
    assert resp.status_code == 302
    assert "location" in resp.headers


def test_forgot_redirect(client: TestClient):
    resp = client.get("/auth/forgot", allow_redirects=False)
    assert resp.status_code == 302
    assert "location" in resp.headers


@pytest.mark.parametrize(
    "code,state",
    [
        ("valid-code", "opaque-state"),
    ],
)
def test_callback_success_redirects_and_sets_cookie(client: TestClient, code: str, state: str):
    # When: GET /auth/callback with a (mock) valid code and state
    resp = client.get(f"/auth/callback?code={code}&state={state}", allow_redirects=False)
    # Then: 302 + both headers present (strict per contract)
    assert resp.status_code == 302
    set_cookie = resp.headers.get("set-cookie", "")
    assert "gustav_session=" in set_cookie
    assert "location" in resp.headers


@pytest.mark.parametrize(
    "code,state",
    [
        ("", "opaque"),
        ("invalid", ""),
        ("invalid", "invalid"),
    ],
)
def test_callback_invalid_returns_400(client: TestClient, code: str, state: str):
    resp = client.get(f"/auth/callback?code={code}&state={state}")
    assert resp.status_code == 400


def test_me_unauthenticated_returns_401(client: TestClient):
    resp = client.get("/api/me")
    assert resp.status_code == 401


def test_logout_requires_authentication(client: TestClient):
    # Without cookie, the security scheme should require auth
    resp = client.post("/auth/logout")
    assert resp.status_code in (401, 403)


def test_logout_clears_cookie(client: TestClient):
    # With a (fake) session cookie, logout should clear it
    cookies = {"gustav_session": "fake-session"}
    resp = client.post("/auth/logout", cookies=cookies, allow_redirects=False)
    assert resp.status_code == 204
    # Contract: server clears the session cookie
    set_cookie = resp.headers.get("set-cookie", "")
    assert "gustav_session=" in set_cookie
    assert "Max-Age=0" in set_cookie or "max-age=0" in set_cookie


def test_me_authenticated_returns_200_and_shape(client: TestClient):
    # With a (fake) session cookie, /api/me should return session shape
    cookies = {"gustav_session": "fake-session"}
    resp = client.get("/api/me", cookies=cookies)
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
