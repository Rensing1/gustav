"""API tests for minting a stable app session from bearer-authenticated BFF requests."""

from __future__ import annotations

from http.cookies import SimpleCookie
from pathlib import Path
import sys

import httpx
import pytest
from httpx import ASGITransport


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore
from identity_access.stores import SessionStore  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


def _mock_bearer_auth(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sub: str,
    roles: list[str],
    name: str,
) -> dict[str, str]:
    monkeypatch.setattr(
        main,
        "verify_bearer_token",
        lambda token, cfg: {
            "sub": sub,
            "name": name,
            "gustav_display_name": name,
            "realm_access": {"roles": roles},
            "exp": 4102444800,
        },
    )
    return {"Authorization": "Bearer test.jwt"}


@pytest.mark.anyio
async def test_session_sync_mints_gustav_session_from_bearer_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    headers = _mock_bearer_auth(monkeypatch, sub="student-sync", roles=["student"], name="Lena")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.post("/api/app/session-sync", headers=headers)

    assert response.status_code == 204
    assert response.headers.get("Cache-Control") == "private, no-store"

    cookie = SimpleCookie()
    cookie.load(response.headers.get("set-cookie", ""))
    morsel = cookie.get(main.SESSION_COOKIE_NAME)
    assert morsel is not None, "session-sync must set gustav_session"
    session_id = morsel.value

    record = store.get(session_id)
    assert record is not None
    assert record.sub == "student-sync"
    assert record.roles == ["student"]
    assert getattr(record, "name", "") == "Lena"


@pytest.mark.anyio
async def test_session_sync_replaces_existing_gustav_session(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    stale = store.create(sub="stale-user", roles=["student"], name="Alt", ttl_seconds=60)
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-sync", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, stale.session_id)
        response = await client.post("/api/app/session-sync", headers=headers)

    assert response.status_code == 204
    assert store.get(stale.session_id) is None, "stale app session should be replaced"

    cookie = SimpleCookie()
    cookie.load(response.headers.get("set-cookie", ""))
    morsel = cookie.get(main.SESSION_COOKIE_NAME)
    assert morsel is not None
    assert morsel.value != stale.session_id
    assert store.get(morsel.value).sub == "teacher-sync"


@pytest.mark.anyio
async def test_session_sync_requires_bearer_even_with_cookie_session(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    rec = store.create(sub="cookie-only", roles=["student"], name="Lena", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, rec.session_id)
        response = await client.post("/api/app/session-sync")

    assert response.status_code == 401
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert response.json() == {"error": "unauthenticated"}
