"""
Teaching Repo DSN enforcement — ensure limited-role DSN by default.

This test does not require a running database: it validates the constructor's
DSN user parsing and enforcement logic.
"""
from __future__ import annotations

import os
import pytest


def test_repo_rejects_service_dsn_by_default(monkeypatch: pytest.MonkeyPatch):
    # Simulate a service role DSN (username not 'gustav_limited')
    bad_dsn = "postgresql://postgres:secret@localhost:5432/postgres"
    # Ensure override is not set
    monkeypatch.delenv("ALLOW_SERVICE_DSN_FOR_TESTING", raising=False)

    # psycopg presence is required by the repo; skip if unavailable
    try:
        import psycopg  # type: ignore  # noqa: F401
    except Exception:
        pytest.skip("psycopg not available")

    from teaching.repo_db import DBTeachingRepo  # type: ignore

    with pytest.raises(RuntimeError):
        DBTeachingRepo(dsn=bad_dsn)


def test_repo_allows_override_flag(monkeypatch: pytest.MonkeyPatch):
    bad_dsn = "postgresql://postgres:secret@localhost:5432/postgres"
    monkeypatch.setenv("ALLOW_SERVICE_DSN_FOR_TESTING", "true")

    try:
        import psycopg  # type: ignore  # noqa: F401
    except Exception:
        pytest.skip("psycopg not available")

    from teaching.repo_db import DBTeachingRepo  # type: ignore

    # Should not raise now (we don't actually connect in constructor)
    DBTeachingRepo(dsn=bad_dsn)


def test_repo_prod_env_requires_explicit_dsn(monkeypatch: pytest.MonkeyPatch):
    """In prod-like environments the repo must not fall back to the dev DSN."""
    try:
        import psycopg  # type: ignore  # noqa: F401
    except Exception:
        pytest.skip("psycopg not available")

    # Simulate production environment without DSN configuration.
    monkeypatch.delenv("TEACHING_DATABASE_URL", raising=False)
    monkeypatch.delenv("TEACHING_DB_URL", raising=False)
    monkeypatch.delenv("RLS_TEST_DSN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.delenv("ALLOW_SERVICE_DSN_FOR_TESTING", raising=False)
    monkeypatch.setenv("GUSTAV_ENV", "prod")

    from teaching import repo_db  # type: ignore

    with pytest.raises(RuntimeError):
        repo_db._dsn()
