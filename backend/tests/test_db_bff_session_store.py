from __future__ import annotations

from dataclasses import dataclass
import types
from typing import Optional

import pytest


@dataclass
class _Record:
    access_token: str
    refresh_token: Optional[str]
    id_token: str
    expires_at: int
    access_token_expires_at: int
    session_expires_at: int


class _FakeCursor:
    def __init__(self, store: dict[str, _Record]) -> None:
        self._store = store
        self._row = None

    def execute(self, sql: str, params: tuple | list) -> None:
        sql_low = (sql or "").lower().strip()

        if sql_low.startswith("insert into"):
            access_token, refresh_token, id_token, legacy_expires_at, access_expires_at, session_expires_at = params
            session_id = f"bff-{len(self._store) + 1}"
            self._store[session_id] = _Record(
                access_token=str(access_token),
                refresh_token=str(refresh_token) if refresh_token is not None else None,
                id_token=str(id_token),
                expires_at=int(legacy_expires_at),
                access_token_expires_at=int(access_expires_at),
                session_expires_at=int(session_expires_at),
            )
            self._row = (session_id,)
            return

        if sql_low.startswith("select"):
            session_id = str(params[0])
            record = self._store.get(session_id)
            self._row = (
                None
                if record is None
                else (
                    session_id,
                    record.access_token,
                    record.refresh_token,
                    record.id_token,
                    record.expires_at,
                    record.access_token_expires_at,
                    record.session_expires_at,
                )
            )
            return

        if sql_low.startswith("update"):
            access_token, refresh_token, id_token, legacy_expires_at, access_expires_at, session_expires_at, session_id = params
            session_id = str(session_id)
            if session_id in self._store:
                self._store[session_id] = _Record(
                    access_token=str(access_token),
                    refresh_token=str(refresh_token) if refresh_token is not None else None,
                    id_token=str(id_token),
                    expires_at=int(legacy_expires_at),
                    access_token_expires_at=int(access_expires_at),
                    session_expires_at=int(session_expires_at),
                )
            self._row = None
            return

        if sql_low.startswith("delete"):
            self._store.pop(str(params[0]), None)
            self._row = None
            return

        raise AssertionError(f"Unexpected SQL in fake psycopg: {sql}")

    def fetchone(self):
        return self._row

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self, store: dict[str, _Record]) -> None:
        self._store = store

    def cursor(self):
        return _FakeCursor(self._store)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _install_fake_psycopg(monkeypatch: pytest.MonkeyPatch, target_module):
    store: dict[str, _Record] = {}

    def fake_connect(dsn: str, autocommit: bool | None = None):
        return _FakeConn(store)

    monkeypatch.setattr(target_module, "HAVE_PSYCOPG", True, raising=False)
    monkeypatch.setattr(
        target_module,
        "psycopg",
        types.SimpleNamespace(connect=fake_connect),
        raising=False,
    )
    return store


def test_db_bff_session_store_reads_refreshable_records(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.identity_access import bff_sessions_db as mod

    _install_fake_psycopg(monkeypatch, mod)
    monkeypatch.setattr(mod, "_now", lambda: 200)
    store = mod.DBBFFSessionStore(dsn="fake://dsn")

    created = store.create(
        access_token="expired-access",
        refresh_token="refresh-token",
        id_token="id-token",
        expires_at=100,
    )

    loaded = store.get(created.session_id)

    assert loaded is not None
    assert loaded.access_token_expires_at == 100
    assert loaded.session_expires_at == 86600


def test_db_bff_session_store_drops_session_after_session_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.identity_access import bff_sessions_db as mod

    _install_fake_psycopg(monkeypatch, mod)
    now_values = iter([0, 200])
    monkeypatch.setattr(mod, "_now", lambda: next(now_values))
    store = mod.DBBFFSessionStore(dsn="fake://dsn", default_ttl_seconds=150)

    created = store.create(
        access_token="expired-access",
        refresh_token="refresh-token",
        id_token="id-token",
        expires_at=100,
    )

    loaded = store.get(created.session_id)

    assert loaded is None
