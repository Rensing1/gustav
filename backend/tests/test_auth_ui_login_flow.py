"""
Auth UI login flow tests (TDD: RED first)

Covers POST /auth/login success path in DEV/CI when AUTH_USE_DIRECT_GRANT is
enabled. We simulate successful direct-grant authentication by monkeypatching
the Keycloak client and the ID token verifier.
"""

import re
from pathlib import Path
import sys
import pytest
import httpx
from httpx import ASGITransport

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore

pytestmark = pytest.mark.anyio("asyncio")


def _extract_csrf(html: str) -> str | None:
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    return m.group(1) if m else None


@pytest.mark.anyio
async def test_login_post_success_sets_session_and_redirects(monkeypatch: pytest.MonkeyPatch):
    # Enable UI flow
    monkeypatch.setattr(main, "AUTH_USE_DIRECT_GRANT", True, raising=False)

    # Fake Keycloak client: return an ID token string
    class FakeKC:
        def __init__(self):
            self.called = False

        def direct_grant(self, *, email: str, password: str) -> dict:
            self.called = True
            assert email == "student@example.com"
            assert password == "Passw0rd!"
            return {"id_token": "stub-token"}

    fake = FakeKC()
    monkeypatch.setattr(main, "KEYCLOAK_CLIENT", fake, raising=False)

    # Stub ID token verification to return realistic claims
    def fake_verify_id_token(id_token: str, cfg):
        assert id_token == "stub-token"
        return {
            "email": "student@example.com",
            "realm_access": {"roles": ["student"]},
            "email_verified": True,
        }

    # Patch the function used by the web module directly
    monkeypatch.setattr(main, "verify_id_token", fake_verify_id_token, raising=False)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        # 1) GET login form to receive CSRF cookie + token
        r1 = await client.get("/auth/login", follow_redirects=False)
        assert r1.status_code == 200
        csrf = _extract_csrf(r1.text)
        assert csrf, "CSRF token missing in HTML"

        # 2) POST credentials including CSRF and a redirect target
        r2 = await client.post(
            "/auth/login",
            data={
                "email": "student@example.com",
                "password": "Passw0rd!",
                "csrf_token": csrf,
                "redirect": "/dashboard",
            },
            follow_redirects=False,
        )
        assert r2.status_code in (302, 303)
        assert r2.headers.get("location", "").endswith("/dashboard")
        set_cookie = r2.headers.get("set-cookie", "")
        assert "gustav_session=" in set_cookie

        # 3) Verify authenticated session
        r3 = await client.get("/api/me")
        assert r3.status_code == 200
        body = r3.json()
        assert body.get("email") == "student@example.com"
        assert body.get("roles") == ["student"]


@pytest.mark.anyio
async def test_login_post_invalid_credentials_returns_400(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main, "AUTH_USE_DIRECT_GRANT", True, raising=False)

    class FakeKC:
        def direct_grant(self, *, email: str, password: str) -> dict:
            raise ValueError("invalid_grant")

    monkeypatch.setattr(main, "KEYCLOAK_CLIENT", FakeKC(), raising=False)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r1 = await client.get("/auth/login", follow_redirects=False)
        csrf = _extract_csrf(r1.text)
        assert csrf
        r2 = await client.post(
            "/auth/login",
            data={
                "email": "student@example.com",
                "password": "wrong",
                "csrf_token": csrf,
            },
            follow_redirects=False,
        )
        assert r2.status_code == 400
