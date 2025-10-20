"""
Lightweight psycopg stand-in for unit tests.

Provides ``install_fake_psycopg`` which monkeypatches a target module so that
``psycopg.connect`` returns an in-memory session store. Designed to support the
subset of SQL used by DBSessionStore tests (INSERT/SELECT/DELETE).
"""
from __future__ import annotations

from dataclasses import dataclass
import time
import types
from typing import Any, Dict, Optional


class FakeJson:
    """Minimal replacement for psycopg.types.json.Json used in tests."""

    def __init__(self, obj: Any) -> None:
        self.obj = obj


@dataclass
class _Record:
    sub: str
    roles: list[str]
    name: str
    id_token: Optional[str]
    expires_at: int


class _FakeCursor:
    def __init__(self, store: Dict[str, _Record], now_func) -> None:
        self._store = store
        self._row = None
        self._rows = None
        self._now = now_func

    def execute(self, sql: str, params: tuple | list) -> None:
        sql_low = (sql or "").lower().strip()
        if sql_low.startswith("insert into"):
            sub, roles_json, name, id_token, expires_at = params
            sid = f"fake-{int(self._now() * 1000)}"
            roles = list(getattr(roles_json, "obj", roles_json))
            self._store[sid] = _Record(
                sub=sub,
                roles=roles,
                name=name,
                id_token=id_token,
                expires_at=int(expires_at),
            )
            self._row = (sid,)
            self._rows = None
        elif sql_low.startswith("select"):
            sid = params[0]
            rec = self._store.get(str(sid))
            if rec and rec.expires_at > int(self._now()):
                self._row = (
                    sid,
                    rec.sub,
                    rec.roles,
                    rec.name,
                    rec.id_token,
                    rec.expires_at,
                )
            else:
                self._row = None
            self._rows = None
        elif sql_low.startswith("delete"):
            sid = params[0]
            self._store.pop(str(sid), None)
            self._row = None
            self._rows = None
        else:
            raise AssertionError(f"Unexpected SQL in fake psycopg: {sql}")

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows or []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self, store: Dict[str, _Record], now_func) -> None:
        self._store = store
        self._now = now_func

    def cursor(self):
        return _FakeCursor(self._store, self._now)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def install_fake_psycopg(monkeypatch, target_module, now_func=time.time):
    """
    Patch ``target_module`` so psycopg operations go against an in-memory store.

    Returns the mutable dictionary acting as the backing store.
    """
    fake_store: Dict[str, _Record] = {}

    def fake_connect(dsn: str, autocommit: bool | None = None):
        return _FakeConn(fake_store, now_func)

    fake_psycopg = types.SimpleNamespace(
        connect=fake_connect,
        types=types.SimpleNamespace(json=types.SimpleNamespace(Json=FakeJson)),
    )

    monkeypatch.setattr(target_module, "HAVE_PSYCOPG", True, raising=False)
    monkeypatch.setattr(target_module, "psycopg", fake_psycopg, raising=False)
    monkeypatch.setattr(target_module, "Json", FakeJson, raising=False)
    return fake_store


__all__ = ["install_fake_psycopg", "FakeJson"]
