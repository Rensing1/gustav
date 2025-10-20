"""
Unit-style tests for DBSessionStore using a fake psycopg driver.

Rationale: Keep CI/self-contained runs green without a real Postgres.
We simulate the subset of psycopg used by DBSessionStore to validate SQL flow
and mapping. No network or external DB required.
"""

from __future__ import annotations

import time
import types
import os
import pytest


class _FakeCursor:
    def __init__(self, store: dict):
        self._store = store
        self._row = None

    def execute(self, sql: str, params: tuple | list):
        sql_low = sql.lower().strip()
        if sql_low.startswith("insert into"):
            sub, roles_json, name, id_token, expires_at = params
            # roles_json is psycopg Json wrapper in real life; accept list here
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
            # params = (session_id,)
            sid = params[0]
            rec = self._store.get(sid)
            if rec and rec["expires_at"] > int(time.time()):
                self._row = (
                    sid,
                    rec["sub"],
                    rec["roles"],
                    rec["name"],
                    rec["id_token"],
                    rec["expires_at"],
                )
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

    # context manager protocol
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self, store: dict):
        self._store = store

    def cursor(self):
        return _FakeCursor(self._store)

    # context manager protocol
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


SESSION_TEST_DSN = os.getenv("SESSION_TEST_DSN")


def _install_fake_psycopg(monkeypatch: pytest.MonkeyPatch, target_module):
    fake_store: dict = {}

    def fake_connect(dsn: str, autocommit: bool | None = None):  # signature-compatible
        return _FakeConn(fake_store)

    # Provide a minimal Json wrapper with .obj attribute to mirror psycopg.types.json.Json
    class FakeJson:
        def __init__(self, obj):
            self.obj = obj

    monkeypatch.setattr(target_module, "HAVE_PSYCOPG", True, raising=False)
    # Replace the psycopg submodule object and its connect + types.json.Json
    fake_psycopg = types.SimpleNamespace(connect=fake_connect, types=types.SimpleNamespace(json=types.SimpleNamespace(Json=FakeJson)))
    monkeypatch.setattr(target_module, "psycopg", fake_psycopg, raising=False)
    # Patch module-level Json import used by DBSessionStore
    monkeypatch.setattr(target_module, "Json", FakeJson, raising=False)
    return fake_store


def test_create_get_delete_roundtrip(monkeypatch: pytest.MonkeyPatch):
    from identity_access import stores_db as mod
    if SESSION_TEST_DSN:
        store = mod.DBSessionStore(dsn=SESSION_TEST_DSN)
    else:
        _install_fake_psycopg(monkeypatch, mod)
        store = mod.DBSessionStore(dsn="fake://dsn")

    rec = store.create(sub="user-1", roles=["student"], name="Max", ttl_seconds=60)
    assert rec.session_id

    got = store.get(rec.session_id)
    assert got is not None
    assert got.sub == "user-1"
    assert got.roles == ["student"]
    assert got.name == "Max"
    assert isinstance(got.expires_at, int)

    store.delete(rec.session_id)
    assert store.get(rec.session_id) is None


def test_get_filters_expired_sessions(monkeypatch: pytest.MonkeyPatch):
    from identity_access import stores_db as mod
    _install_fake_psycopg(monkeypatch, mod)
    store = mod.DBSessionStore(dsn="fake://dsn")

    rec = store.create(sub="u2", roles=["student"], name="Expired", ttl_seconds=-10)
    assert rec.session_id
    assert store.get(rec.session_id) is None


def test_invalid_table_name_is_rejected(monkeypatch: pytest.MonkeyPatch):
    from identity_access import stores_db as mod
    _install_fake_psycopg(monkeypatch, mod)
    import pytest as _pytest
    with _pytest.raises(ValueError):
        mod.DBSessionStore(dsn="fake://dsn", table="bad;drop table")

    # Valid fully-qualified name should pass
    store = mod.DBSessionStore(dsn="fake://dsn", table="public.app_sessions")
    assert store is not None


def test_missing_dsn_raises_runtime_error(monkeypatch: pytest.MonkeyPatch):
    """DBSessionStore should fail fast when no DSN is provided via arg or env."""
    from identity_access import stores_db as mod
    # Pretend psycopg is available, but do not set any DSN env var
    _install_fake_psycopg(monkeypatch, mod)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    import pytest as _pytest
    with _pytest.raises(RuntimeError):
        mod.DBSessionStore()  # type: ignore[arg-type]
