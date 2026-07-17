"""Contracts for verified TLS in the production-like E2E profile."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.tests_e2e import conftest as e2e_conftest


ROOT = Path(__file__).resolve().parents[2]


def test_e2e_configuration_never_monkeypatches_requests_tls() -> None:
    source = (ROOT / "backend/tests_e2e/conftest.py").read_text(encoding="utf-8")

    assert "verify=False" not in source
    assert "Session.request" not in source
    assert "REQUESTS_CA_BUNDLE" in source
    assert "E2E_VERIFY_TLS" in source


def test_make_e2e_requires_the_caddy_ca_and_tls_verification() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    body = makefile.split("test-e2e:", 1)[1].split(".PHONY:", 1)[0]

    assert "E2E_VERIFY_TLS=1" in body
    assert "REQUESTS_CA_BUNDLE=.tmp/caddy-root.crt" in body
    assert "curl --cacert .tmp/caddy-root.crt" in body
    assert "curl -sk" not in body


def test_e2e_fails_fast_when_tls_verification_is_not_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUN_E2E", "1")
    monkeypatch.delenv("E2E_VERIFY_TLS", raising=False)
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)

    with pytest.raises(pytest.UsageError, match="E2E_VERIFY_TLS=1"):
        e2e_conftest._configure_requests_tls_for_local_e2e()


def test_e2e_fails_fast_when_caddy_ca_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("RUN_E2E", "1")
    monkeypatch.setenv("E2E_VERIFY_TLS", "1")
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(tmp_path / "missing.crt"))

    with pytest.raises(pytest.UsageError, match="Caddy root CA"):
        e2e_conftest._configure_requests_tls_for_local_e2e()
