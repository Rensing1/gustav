"""Tests for DB test-target safety checks."""

from __future__ import annotations

from backend.tests.utils import db


def test_local_database_dsn_is_allowed_without_explicit_isolation(monkeypatch) -> None:
    monkeypatch.delenv("GUSTAV_DB_TEST_MODE", raising=False)
    monkeypatch.delenv("GUSTAV_TEST_RUN_ID", raising=False)

    assert db.is_safe_db_test_dsn("postgresql://gustav_app:pw@127.0.0.1:54322/postgres")


def test_remote_database_dsn_requires_explicit_isolation(monkeypatch) -> None:
    monkeypatch.delenv("GUSTAV_DB_TEST_MODE", raising=False)
    monkeypatch.delenv("GUSTAV_TEST_RUN_ID", raising=False)

    assert not db.is_safe_db_test_dsn("postgresql://gustav_app:pw@db.school.example/postgres")


def test_remote_database_dsn_is_allowed_with_explicit_isolation(monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_DB_TEST_MODE", "isolated")
    monkeypatch.setenv("GUSTAV_TEST_RUN_ID", "pytest-safe-batch")

    assert db.is_safe_db_test_dsn("postgresql://gustav_app:pw@db.school.example/postgres")
