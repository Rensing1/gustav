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

