"""API tests for minting a stable app session from bearer-authenticated BFF requests."""

from __future__ import annotations

from http.cookies import SimpleCookie
import importlib
from types import SimpleNamespace

import httpx
import pytest
from httpx import ASGITransport

from backend.tests.runtime_auth_helpers import install_session_store

main = importlib.import_module("backend.web.main")


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
    store = install_session_store(monkeypatch, main)
    headers = _mock_bearer_auth(monkeypatch, sub="student-sync", roles=["student"], name="Lena")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.post(
            "/api/app/session-sync",
            headers=headers,
            json={"id_token": "id-token-sync-1"},
        )

    assert response.status_code == 204
    assert response.headers.get("Cache-Control") == "private, no-store"

    cookie = SimpleCookie()
    cookie.load(response.headers.get("set-cookie", ""))
    morsel = cookie.get(main.SESSION_COOKIE_NAME)
    assert morsel is not None, "session-sync must set gustav_session"
    assert not morsel["domain"], "gustav_session must stay host-only"
    assert morsel["httponly"]
    assert morsel["secure"]
    assert morsel["samesite"].lower() == "lax"
    session_id = morsel.value

    record = store.get(session_id)
    assert record is not None
    assert record.sub == "student-sync"
    assert record.roles == ["student"]
    assert getattr(record, "name", "") == "Lena"
    assert getattr(record, "id_token", None) == "id-token-sync-1"


@pytest.mark.anyio
async def test_session_sync_replaces_existing_gustav_session(monkeypatch: pytest.MonkeyPatch) -> None:
    store = install_session_store(monkeypatch, main)
    stale = store.create(sub="stale-user", roles=["student"], name="Alt", ttl_seconds=60)
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-sync", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, stale.session_id)
        response = await client.post(
            "/api/app/session-sync",
            headers=headers,
            json={"id_token": "id-token-sync-2"},
        )

    assert response.status_code == 204
    assert store.get(stale.session_id) is None, "stale app session should be replaced"

    cookie = SimpleCookie()
    cookie.load(response.headers.get("set-cookie", ""))
    morsel = cookie.get(main.SESSION_COOKIE_NAME)
    assert morsel is not None
    assert not morsel["domain"], "replacement gustav_session must stay host-only"
    assert morsel["httponly"]
    assert morsel["secure"]
    assert morsel["samesite"].lower() == "lax"
    assert morsel.value != stale.session_id
    assert store.get(morsel.value).sub == "teacher-sync"
    assert getattr(store.get(morsel.value), "id_token", None) == "id-token-sync-2"


@pytest.mark.anyio
async def test_session_sync_requires_bearer_even_with_cookie_session(monkeypatch: pytest.MonkeyPatch) -> None:
    store = install_session_store(monkeypatch, main)
    rec = store.create(sub="cookie-only", roles=["student"], name="Lena", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, rec.session_id)
        response = await client.post("/api/app/session-sync")

    assert response.status_code == 401
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert response.json() == {"error": "unauthenticated"}


@pytest.mark.anyio
async def test_session_sync_uses_app_runtime_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = install_session_store(monkeypatch, main)
    monkeypatch.setattr(main.app.state, "main_module", SimpleNamespace(SESSION_COOKIE_NAME=main.SESSION_COOKIE_NAME))
    headers = _mock_bearer_auth(monkeypatch, sub="runtime-sync", roles=["student"], name="Runtime")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.post(
            "/api/app/session-sync",
            headers=headers,
            json={"id_token": "id-token-runtime"},
        )

    assert response.status_code == 204
    cookie = SimpleCookie()
    cookie.load(response.headers.get("set-cookie", ""))
    morsel = cookie.get(main.SESSION_COOKIE_NAME)
    assert morsel is not None
    record = store.get(morsel.value)
    assert record is not None
    assert record.sub == "runtime-sync"
    assert getattr(record, "id_token", None) == "id-token-runtime"
