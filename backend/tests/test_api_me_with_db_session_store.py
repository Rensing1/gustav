"""
Integration test: /api/me with DBSessionStore using a fake psycopg driver.

Why: Ensure the web adapter works with the DB-backed session store without
requiring a real Postgres/Supabase during unit/contract test runs.
"""

from __future__ import annotations

import types
import time
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
                self._row = (sid, rec["sub"], rec["roles"], rec["name"], rec["expires_at"])
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


@pytest.mark.anyio
async def test_api_me_with_db_session_store(monkeypatch: pytest.MonkeyPatch):
    # Wire DBSessionStore with fake psycopg
    from identity_access import stores_db as mod
    _install_fake_psycopg(monkeypatch, mod)
    store = mod.DBSessionStore(dsn="fake://dsn")

    # Swap the session store used by the web app
    monkeypatch.setattr(main, "SESSION_STORE", store)

    # Create a DB-backed session and call /api/me with the cookie
    rec = store.create(sub="user-42", roles=["student"], name="Max Musterschüler", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", rec.session_id)
        resp = await client.get("/api/me")

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("sub") == "user-42"
    assert body.get("roles") == ["student"]
    assert body.get("name") == "Max Musterschüler"

