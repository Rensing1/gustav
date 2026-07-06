"""Environment guards shared by backend pytest configuration.

Why:
    The default backend test suite must stay hermetic. Integration suites may
    opt into external wiring, but only with explicit RUN_* flags and markers.
"""

from __future__ import annotations

import os

import pytest


def truthy_env(name: str) -> bool:
    """Return whether an environment flag uses a conventional truthy value."""

    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def _is_prod_like(env_value: str | None) -> bool:
    return (env_value or "").strip().lower() in {"prod", "production", "stage", "staging"}


def guard_against_prod_env_during_pytest() -> None:
    """Prevent import-time SystemExit when a developer exported prod-like env vars.

    Why:
        `backend/web/main.py` calls the startup security guard at import time.
        If a developer has `GUSTAV_ENV=prod` exported in their shell, pytest
        collection would abort unless all production secrets are configured.
    """

    # Ensure application modules never auto-load `.env` during pytest collection.
    # Integration suites that need `.env` load it explicitly in `pytest_configure`.
    os.environ.setdefault("GUSTAV_ENABLE_DOTENV", "false")
    if _is_prod_like(os.getenv("GUSTAV_ENV")):
        os.environ["GUSTAV_ENV"] = "dev"


def prune_external_wiring_env_by_default() -> None:
    """Keep the default unit/in-process suite independent from external services."""

    if truthy_env("RUN_E2E") or truthy_env("RUN_SUPABASE_E2E") or truthy_env("RUN_OPENAI_E2E"):
        return
    for var in (
        "SUPABASE_URL",
        "SUPABASE_PUBLIC_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
    ):
        os.environ.pop(var, None)
    for var in (
        "KC_BASE_URL",
        "KC_PUBLIC_BASE_URL",
    ):
        os.environ.pop(var, None)


def configure_pytest_environment(config: pytest.Config) -> None:
    """Load `.env` only for explicitly selected integration suites.

    Contract:
        - Unit/in-process suite (`pytest` / `make test`) must not depend on `.env`.
        - E2E requires RUN_E2E=1 and uses `-m e2e`.
        - Supabase integration requires RUN_SUPABASE_E2E=1 and uses `-m supabase_integration`.
        - OpenAI integration requires RUN_OPENAI_E2E=1 and uses `-m openai_integration`.
    """

    markexpr = (getattr(config.option, "markexpr", "") or "").strip()

    if truthy_env("RUN_E2E") and not markexpr:
        raise pytest.UsageError("RUN_E2E=1 requires marker selection. Use `make test-e2e` or `pytest -m e2e`.")
    if truthy_env("RUN_SUPABASE_E2E") and not markexpr:
        raise pytest.UsageError(
            "RUN_SUPABASE_E2E=1 requires marker selection. Use `make test-supabase` or `pytest -m supabase_integration`."
        )
    if truthy_env("RUN_OPENAI_E2E") and not markexpr:
        raise pytest.UsageError(
            "RUN_OPENAI_E2E=1 requires marker selection. Use `make test-openai` or `pytest -m openai_integration`."
        )

    if not (truthy_env("RUN_E2E") or truthy_env("RUN_SUPABASE_E2E") or truthy_env("RUN_OPENAI_E2E")):
        return

    try:
        from dotenv import load_dotenv  # type: ignore

        # Load `.env` as defaults; explicit env vars such as Makefile overrides
        # must take precedence.
        load_dotenv(override=False)
    except Exception:
        # `.env` loading is best-effort; integration tests fail with a clear
        # message when required vars are missing.
        return
