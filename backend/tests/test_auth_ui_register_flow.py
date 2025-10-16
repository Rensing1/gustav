"""
Auth UI registration flow tests (TDD: RED phase)

Covers POST /auth/register in DEV/CI when AUTH_USE_DIRECT_GRANT is enabled.
We mock the Keycloak admin client to assert behavior:
 - Happy path: user is created, 'student' role assigned, 303 redirect to login with login_hint
 - Duplicate: create_user raises -> 400
 - Role assignment failure: assign role raises -> 500
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
async def test_register_post_happy_path_redirects_to_login(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main, "AUTH_USE_DIRECT_GRANT", True, raising=False)

    class FakeAdmin:
        def __init__(self):
            self.created = []
            self.assigned = []

        def create_user(self, *, email: str, password: str, display_name: str | None = None) -> str:
            self.created.append((email, bool(password), display_name))
            return "user-123"

        def assign_realm_role(self, *, user_id: str, role_name: str) -> None:
            assert user_id == "user-123"
            self.assigned.append(role_name)

    fake = FakeAdmin()
    monkeypatch.setattr(main, "KEYCLOAK_ADMIN", fake, raising=False)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r1 = await client.get("/auth/register", follow_redirects=False)
        assert r1.status_code == 200
        csrf = _extract_csrf(r1.text)
        assert csrf

        r2 = await client.post(
            "/auth/register",
            data={
                "email": "new@example.com",
                "password": "Passw0rd!",
                "display_name": "New Student",
                "csrf_token": csrf,
            },
            follow_redirects=False,
        )
        assert r2.status_code in (302, 303)
        from urllib.parse import urlparse, parse_qs
        loc = r2.headers.get("location", "")
        assert "/auth/login" in loc
        qs = parse_qs(urlparse(loc).query)
        assert qs.get("login_hint") == ["new@example.com"]
        set_cookie = r2.headers.get("set-cookie", "")
        assert "gustav_session=" not in set_cookie  # no auto-login
        # Verify interactions
        assert fake.created and fake.assigned == ["student"]


@pytest.mark.anyio
async def test_register_post_duplicate_returns_400(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main, "AUTH_USE_DIRECT_GRANT", True, raising=False)

    class FakeAdmin:
        def create_user(self, *, email: str, password: str, display_name: str | None = None) -> str:
            raise ValueError("duplicate")

        def assign_realm_role(self, *, user_id: str, role_name: str) -> None:
            raise AssertionError("should not be called")

    monkeypatch.setattr(main, "KEYCLOAK_ADMIN", FakeAdmin(), raising=False)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r1 = await client.get("/auth/register", follow_redirects=False)
        csrf = _extract_csrf(r1.text)
        assert csrf
        r2 = await client.post(
            "/auth/register",
            data={
                "email": "new@example.com",
                "password": "weak",
                "csrf_token": csrf,
            },
            follow_redirects=False,
        )
        assert r2.status_code == 400


@pytest.mark.anyio
async def test_register_post_role_assignment_failure_returns_500(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main, "AUTH_USE_DIRECT_GRANT", True, raising=False)

    class FakeAdmin:
        def create_user(self, *, email: str, password: str, display_name: str | None = None) -> str:
            return "user-999"

        def assign_realm_role(self, *, user_id: str, role_name: str) -> None:
            raise RuntimeError("role assign failed")

    monkeypatch.setattr(main, "KEYCLOAK_ADMIN", FakeAdmin(), raising=False)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r1 = await client.get("/auth/register", follow_redirects=False)
        csrf = _extract_csrf(r1.text)
        r2 = await client.post(
            "/auth/register",
            data={
                "email": "new@example.com",
                "password": "Passw0rd!",
                "csrf_token": csrf,
            },
            follow_redirects=False,
        )
        assert r2.status_code == 500
