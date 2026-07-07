from __future__ import annotations

import pytest

from backend.learning.workers import runtime_config


def _reset_worker_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [
        "WORKER_BACKOFF_SECONDS",
        "WORKER_CONCURRENCY",
        "WORKER_LEASE_SECONDS",
        "WORKER_LEASE_MULTIPLIER",
        "LEARNING_WORKER_DATABASE_URL",
        "LEARNING_WORKER_DB_URL",
        "LEARNING_DATABASE_URL",
        "LEARNING_DB_URL",
        "LEARNING_WORKER_DB_USER",
        "LEARNING_WORKER_DB_PASSWORD",
        "ALLOW_SERVICE_DSN_FOR_TESTING",
        "RUN_E2E",
        "RUN_SUPABASE_E2E",
        "TEST_DB_HOST",
        "TEST_DB_PORT",
    ]:
        monkeypatch.delenv(name, raising=False)


def test_worker_runtime_config_clamps_backoff_concurrency_and_lease(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_worker_env(monkeypatch)
    monkeypatch.setenv("WORKER_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("WORKER_CONCURRENCY", "10")
    monkeypatch.setenv("WORKER_LEASE_SECONDS", "2")
    monkeypatch.setenv("WORKER_LEASE_MULTIPLIER", "4")

    assert runtime_config.backoff_seconds() == 1
    assert runtime_config.concurrency_limit() == runtime_config.MAX_CONCURRENCY
    assert runtime_config.lease_duration_seconds() == 8


def test_worker_runtime_config_uses_safe_defaults_for_invalid_numbers(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_worker_env(monkeypatch)
    monkeypatch.setenv("WORKER_BACKOFF_SECONDS", "invalid")
    monkeypatch.setenv("WORKER_CONCURRENCY", "invalid")
    monkeypatch.setenv("WORKER_LEASE_SECONDS", "invalid")
    monkeypatch.setenv("WORKER_LEASE_MULTIPLIER", "invalid")

    assert runtime_config.backoff_seconds() == 10
    assert runtime_config.concurrency_limit() == 1
    assert runtime_config.lease_duration_seconds() == 180


def test_worker_runtime_config_rejects_service_role_dsn_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_worker_env(monkeypatch)
    monkeypatch.setenv("LEARNING_WORKER_DATABASE_URL", "postgresql://postgres:pw@db:5432/postgres")

    with pytest.raises(RuntimeError, match="gustav_worker"):
        runtime_config.resolve_worker_dsn()


def test_worker_runtime_config_builds_dedicated_worker_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_worker_env(monkeypatch)
    monkeypatch.setenv("LEARNING_WORKER_DB_USER", "gustav_worker")
    monkeypatch.setenv("LEARNING_WORKER_DB_PASSWORD", "pw")
    monkeypatch.setenv("TEST_DB_HOST", "db")
    monkeypatch.setenv("TEST_DB_PORT", "6543")

    assert runtime_config.resolve_worker_dsn() == "postgresql://gustav_worker:pw@db:6543/postgres"


def test_worker_runtime_config_allows_service_dsn_only_when_explicitly_opted_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reset_worker_env(monkeypatch)
    monkeypatch.setenv("LEARNING_WORKER_DATABASE_URL", "postgresql://postgres:pw@db:5432/postgres")
    monkeypatch.setenv("ALLOW_SERVICE_DSN_FOR_TESTING", "true")

    assert runtime_config.resolve_worker_dsn() == "postgresql://postgres:pw@db:5432/postgres"
