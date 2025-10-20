"""
Unit-style tests for DBSessionStore using a fake psycopg driver.

Rationale: Keep CI/self-contained runs green without a real Postgres.
We simulate the subset of psycopg used by DBSessionStore to validate SQL flow
and mapping. No network or external DB required.
"""

from __future__ import annotations

import os
import pytest

from backend.tests.utils.fake_psycopg import install_fake_psycopg


SESSION_TEST_DSN = os.getenv("SESSION_TEST_DSN")


def test_create_get_delete_roundtrip(monkeypatch: pytest.MonkeyPatch):
    from identity_access import stores_db as mod
    if SESSION_TEST_DSN:
        store = mod.DBSessionStore(dsn=SESSION_TEST_DSN)
    else:
        install_fake_psycopg(monkeypatch, mod)
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
    install_fake_psycopg(monkeypatch, mod)
    store = mod.DBSessionStore(dsn="fake://dsn")

    rec = store.create(sub="u2", roles=["student"], name="Expired", ttl_seconds=-10)
    assert rec.session_id
    assert store.get(rec.session_id) is None


def test_invalid_table_name_is_rejected(monkeypatch: pytest.MonkeyPatch):
    from identity_access import stores_db as mod
    install_fake_psycopg(monkeypatch, mod)
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
    install_fake_psycopg(monkeypatch, mod)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    import pytest as _pytest
    with _pytest.raises(RuntimeError):
        mod.DBSessionStore()  # type: ignore[arg-type]
