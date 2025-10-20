"""
Integration test: /api/me with DBSessionStore using a fake psycopg driver.

Why: Ensure the web adapter works with the DB-backed session store without
requiring a real Postgres/Supabase during unit/contract test runs.
"""

from __future__ import annotations

import types
import time
import os
import pytest
import httpx
from httpx import ASGITransport
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


SESSION_TEST_DSN = os.getenv("SESSION_TEST_DSN")


class _FakeCursor:
    def __init__(self, store: dict):
        self._store = store
        self._row = None

    def execute(self, sql: str, params: tuple | list):
        sql_low = (sql or "").lower().strip()
        if sql_low.startswith("insert into"):
            sub, roles_json, name, id_token, expires_at = params
            sid = f"fake-{int(time.time()*1000)}"
            self._store[sid] = {
                "sub": sub,
                "roles": list(getattr(roles_json, "obj", roles_json)),
                "name": name,
                "id_token": id_token,
                "expires_at": int(expires_at),
            }
            self._row = (sid,)
        elif sql_low.startswith("select"):
            sid = params[0]
            rec = self._store.get(sid)
            now = int(time.time())
            if rec and rec["expires_at"] > now:
                self._row = (sid, rec["sub"], rec["roles"], rec["name"], rec["id_token"], rec["expires_at"])
            else:
                self._row = None
        elif sql_low.startswith("delete"):
            sid = params[0]
            self._store.pop(sid, None)
            self._row = None
        else:
            raise AssertionError(f"Unexpected SQL: {sql}")

    def fetchone(self):
        return self._row

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self, store: dict):
        self._store = store

    def cursor(self):
        return _FakeCursor(self._store)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _install_fake_psycopg(monkeypatch: pytest.MonkeyPatch, target_module):
    fake_store: dict = {}

    def fake_connect(dsn: str, autocommit: bool | None = None):
        return _FakeConn(fake_store)

    class FakeJson:
        def __init__(self, obj):
            self.obj = obj

    # Enable DB path and provide fake driver + Json wrapper
    monkeypatch.setattr(target_module, "HAVE_PSYCOPG", True, raising=False)
    fake_psycopg = types.SimpleNamespace(connect=fake_connect, types=types.SimpleNamespace(json=types.SimpleNamespace(Json=FakeJson)))
    monkeypatch.setattr(target_module, "psycopg", fake_psycopg, raising=False)
    monkeypatch.setattr(target_module, "Json", FakeJson, raising=False)
    return fake_store


def _prepare_store(monkeypatch: pytest.MonkeyPatch):
    from identity_access import stores_db as mod
    if SESSION_TEST_DSN:
        # Real database path (requires psycopg and migration applied)
        store = mod.DBSessionStore(dsn=SESSION_TEST_DSN)
        fake_store = None
    else:
        fake_store = _install_fake_psycopg(monkeypatch, mod)
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
    """If the DB-backed session is expired, /api/me must return 401 with no-store."""
    store, _ = _prepare_store(monkeypatch)
    monkeypatch.setattr(main, "SESSION_STORE", store)

    rec = store.create(sub="user-expired", roles=["student"], name="Expired", ttl_seconds=-5)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", rec.session_id)
        resp = await client.get("/api/me")

    try:
        assert resp.status_code == 401
        assert resp.headers.get("Cache-Control") == "no-store"
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
