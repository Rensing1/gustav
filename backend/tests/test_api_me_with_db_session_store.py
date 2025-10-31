"""
Integration test: /api/me with DBSessionStore using a fake psycopg driver.

Why: Ensure the web adapter works with the DB-backed session store without
requiring a real Postgres/Supabase during unit/contract test runs.
"""

from __future__ import annotations

import os
import pytest
import httpx
from httpx import ASGITransport
from pathlib import Path
import sys

from backend.tests.utils.fake_psycopg import install_fake_psycopg


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


SESSION_TEST_DSN = os.getenv("SESSION_TEST_DSN")


def _prepare_store(monkeypatch: pytest.MonkeyPatch):
    from identity_access import stores_db as mod
    if SESSION_TEST_DSN:
        # Real database path (requires psycopg and migration applied)
        store = mod.DBSessionStore(dsn=SESSION_TEST_DSN)
        fake_store = None
    else:
        fake_store = install_fake_psycopg(monkeypatch, mod)
        store = mod.DBSessionStore(dsn="fake://dsn")
    return store, fake_store


def _cleanup_store(store, rec):
    try:
        store.delete(rec.session_id)
    except Exception:
        pass


@pytest.mark.anyio
async def test_api_me_with_db_session_store(monkeypatch: pytest.MonkeyPatch):
    store, _ = _prepare_store(monkeypatch)

    monkeypatch.setattr(main, "SESSION_STORE", store)

    rec = store.create(sub="user-42", roles=["student"], name="Max Musterschüler", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", rec.session_id)
        resp = await client.get("/api/me")

    try:
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("sub") == "user-42"
        assert body.get("roles") == ["student"]
        assert body.get("name") == "Max Musterschüler"
    finally:
        _cleanup_store(store, rec)


@pytest.mark.anyio
async def test_api_me_with_db_store_expired_session_returns_401(monkeypatch: pytest.MonkeyPatch):
    """If the DB-backed session is expired, /api/me must return 401 with private no-store headers."""
    store, _ = _prepare_store(monkeypatch)
    monkeypatch.setattr(main, "SESSION_STORE", store)

    rec = store.create(sub="user-expired", roles=["student"], name="Expired", ttl_seconds=-5)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", rec.session_id)
        resp = await client.get("/api/me")

    try:
        assert resp.status_code == 401
        assert resp.headers.get("Cache-Control") == "private, no-store"
        assert resp.json().get("error") == "unauthenticated"
    finally:
        _cleanup_store(store, rec)


@pytest.mark.anyio
async def test_logout_deletes_session_and_clears_cookie_with_db_store(monkeypatch: pytest.MonkeyPatch):
    """/auth/logout should delete the DB session and clear the cookie."""
    store, _ = _prepare_store(monkeypatch)
    monkeypatch.setattr(main, "SESSION_STORE", store)

    rec = store.create(sub="user-logout", roles=["student"], name="Max", ttl_seconds=60, id_token="idtok")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", rec.session_id)
        resp = await client.get("/auth/logout", follow_redirects=False)

    try:
        assert resp.status_code in (301, 302, 303)
        set_cookie = resp.headers.get("set-cookie", "")
        assert "gustav_session=" in set_cookie
        assert "Max-Age=0" in set_cookie or "max-age=0" in set_cookie
        assert store.get(rec.session_id) is None
    finally:
        _cleanup_store(store, rec)
