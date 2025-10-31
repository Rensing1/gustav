"""
Security config guard tests (TDD first).

Validates that production/staging environments fail fast when the Supabase
Service Role key is unset or a dummy placeholder, while development allows
running with a dummy key for local convenience.
"""
from __future__ import annotations

import importlib
import os
import types

import pytest


@pytest.mark.anyio
async def test_service_role_key_guard_prod_raises(monkeypatch: pytest.MonkeyPatch):
    """In prod-like env, a dummy/unset service role key must abort startup."""
    # Arrange: ensure env looks like production
    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "DUMMY_DO_NOT_USE")

    # Act/Assert
    # Import the config module and call the guard; it must raise SystemExit
    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    with pytest.raises(SystemExit):
        cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_service_role_key_guard_dev_allows_dummy(monkeypatch: pytest.MonkeyPatch):
    """In dev env, a dummy service role key is tolerated for local setups."""
    # Arrange: dev defaults
    monkeypatch.setenv("GUSTAV_ENV", "dev")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "DUMMY_DO_NOT_USE")

    # Act/Assert: should not raise
    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_dsn_user_guard_prod_raises_if_limited_user(monkeypatch: pytest.MonkeyPatch):
    """In prod-like env, DSN must not authenticate as the app role."""
    monkeypatch.setenv("GUSTAV_ENV", "production")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "REAL_NON_DUMMY")
    # Valid TLS setting
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://gustav_limited:secret@db.example.com:5432/postgres?sslmode=require",
    )

    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    with pytest.raises(SystemExit):
        cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_dsn_user_guard_prod_allows_nonlimited_user(monkeypatch: pytest.MonkeyPatch):
    """In prod-like env, a separate login IN ROLE gustav_limited is allowed."""
    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "REAL_NON_DUMMY")
    monkeypatch.setenv("KC_ADMIN_CLIENT_SECRET", "REAL_NON_DUMMY")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://gustav_app:strong@db.example.com:5432/postgres?sslmode=require",
    )

    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    # Should not raise
    cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_kc_admin_client_secret_guard_prod_raises(monkeypatch: pytest.MonkeyPatch):
    """In prod-like env, a missing or placeholder KC admin client secret must abort startup."""
    # Arrange: prod with valid Supabase key so that only KC secret is tested
    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "REAL_NON_DUMMY")
    # Placeholder secret must be rejected
    monkeypatch.setenv("KC_ADMIN_CLIENT_SECRET", "CHANGE_ME_DEV")

    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    with pytest.raises(SystemExit):
        cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_kc_admin_client_secret_guard_dev_allows_placeholder(monkeypatch: pytest.MonkeyPatch):
    """In dev env, a placeholder KC admin client secret is tolerated for local setups."""
    monkeypatch.setenv("GUSTAV_ENV", "dev")
    # Dev also tolerates dummy Supabase
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "DUMMY_DO_NOT_USE")
    monkeypatch.setenv("KC_ADMIN_CLIENT_SECRET", "CHANGE_ME_DEV")

    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    # Should not raise
    cfg.ensure_secure_config_on_startup()
