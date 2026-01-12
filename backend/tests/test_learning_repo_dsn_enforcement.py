"""
Learning Repo DSN enforcement — prod-like environments must fail fast.

Why:
    "Local = prod" means that production/staging environments must never
    silently fall back to a local dev DSN. If the DSN is not configured
    explicitly, startup must fail early and loudly.

Note:
    This is a pure configuration test; it does not require a running database.
"""

from __future__ import annotations

import pytest


@pytest.mark.parametrize("env", ["prod", "production", "stage", "staging"])
def test_learning_repo_prod_like_env_requires_explicit_dsn(monkeypatch: pytest.MonkeyPatch, env: str) -> None:
    monkeypatch.delenv("LEARNING_DATABASE_URL", raising=False)
    monkeypatch.delenv("LEARNING_DB_URL", raising=False)
    monkeypatch.delenv("RLS_TEST_DSN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("GUSTAV_ENV", env)

    from backend.learning import repo_db

    with pytest.raises(RuntimeError):
        repo_db._dsn()


def test_learning_repo_dev_env_falls_back_to_default_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LEARNING_DATABASE_URL", raising=False)
    monkeypatch.delenv("LEARNING_DB_URL", raising=False)
    monkeypatch.delenv("RLS_TEST_DSN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("GUSTAV_ENV", "dev")

    monkeypatch.setenv("TEST_DB_HOST", "db.example.invalid")
    monkeypatch.setenv("TEST_DB_PORT", "54322")
    monkeypatch.setenv("APP_DB_USER", "gustav_app")
    monkeypatch.setenv("APP_DB_PASSWORD", "secret")

    from backend.learning import repo_db

    assert repo_db._dsn() == repo_db._default_app_login_dsn()

