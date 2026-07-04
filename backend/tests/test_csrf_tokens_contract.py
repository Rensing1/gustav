"""Contracts for SSR CSRF token helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.web.csrf_tokens import (
    csrf_signing_secret,
    csrf_ttl_seconds,
    get_or_create_csrf_token,
    sign_csrf_token,
    validate_csrf,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_csrf_ttl_seconds_defaults_clamps_and_ignores_invalid_env(monkeypatch) -> None:
    """CSRF tokens inherit the app-session horizon but remain bounded."""

    monkeypatch.delenv("APP_SESSION_TTL_SECONDS", raising=False)
    monkeypatch.delenv("APP_CSRF_TTL_SECONDS", raising=False)
    assert csrf_ttl_seconds() == 24 * 60 * 60

    monkeypatch.setenv("APP_CSRF_TTL_SECONDS", "1")
    assert csrf_ttl_seconds() == 60

    monkeypatch.setenv("APP_CSRF_TTL_SECONDS", str(8 * 24 * 60 * 60))
    assert csrf_ttl_seconds() == 7 * 24 * 60 * 60

    monkeypatch.setenv("APP_CSRF_TTL_SECONDS", "not-an-int")
    assert csrf_ttl_seconds() == 24 * 60 * 60


def test_csrf_signing_secret_uses_explicit_secret_and_fails_closed_in_prod(monkeypatch) -> None:
    """Prod-like environments must not silently use a process-random CSRF secret."""

    monkeypatch.setenv("APP_CSRF_TOKEN_SECRET", "real-csrf-secret")
    monkeypatch.setenv("GUSTAV_ENV", "prod")
    assert csrf_signing_secret() == b"real-csrf-secret"

    monkeypatch.delenv("APP_CSRF_TOKEN_SECRET", raising=False)
    monkeypatch.delenv("H5P_REVIEW_TOKEN_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="APP_CSRF_TOKEN_SECRET"):
        csrf_signing_secret()


def test_csrf_token_roundtrip_rejects_wrong_session_and_expired_token(monkeypatch) -> None:
    """A token is bound to session id and expiry timestamp."""

    monkeypatch.setenv("APP_CSRF_TOKEN_SECRET", "real-csrf-secret")
    token = get_or_create_csrf_token("session-a")

    assert validate_csrf("session-a", token)
    assert not validate_csrf("session-b", token)

    expired_sig = sign_csrf_token(session_id="session-a", expires_at=1)
    assert not validate_csrf("session-a", f"v1.1.{expired_sig}")


def test_main_does_not_own_or_import_csrf_token_logic() -> None:
    """The app entry module should render passed CSRF tokens, not own token crypto."""

    main_source = (REPO_ROOT / "backend/web/main.py").read_text(encoding="utf-8")

    for retired_helper in (
        "_CSRF_BY_SESSION",
        "_DEV_CSRF_SIGNING_SECRET",
        "def _csrf_ttl_seconds",
        "def _csrf_signing_secret",
        "def _sign_csrf_token",
        "def _get_or_create_csrf_token",
        "def _validate_csrf",
    ):
        assert retired_helper not in main_source

    assert "backend.web.csrf_tokens" not in main_source
    assert "get_or_create_csrf_token(" not in main_source
