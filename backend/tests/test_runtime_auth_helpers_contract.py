"""Contracts for auth runtime helpers used by tests.

Why:
    Runtime-first auth tests should not need to write directly to
    `main.RUNTIME.session_store`. Small helpers keep the runtime object as the
    only test surface for auth collaborators.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.identity_access.stores import SessionStore, StateStore


def test_install_session_store_updates_runtime_without_main_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.tests.runtime_auth_helpers import install_session_store

    runtime_store = SessionStore()
    main_module = SimpleNamespace(
        RUNTIME=SimpleNamespace(session_store=SessionStore()),
    )

    installed = install_session_store(monkeypatch, main_module, runtime_store)

    assert installed is runtime_store
    assert main_module.RUNTIME.session_store is runtime_store
    assert not hasattr(main_module, "SESSION_STORE")


def test_install_state_store_updates_runtime_without_main_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.tests.runtime_auth_helpers import install_state_store

    runtime_store = StateStore()
    main_module = SimpleNamespace(
        RUNTIME=SimpleNamespace(state_store=StateStore()),
    )

    installed = install_state_store(monkeypatch, main_module, runtime_store)

    assert installed is runtime_store
    assert main_module.RUNTIME.state_store is runtime_store
    assert not hasattr(main_module, "STATE_STORE")


def test_install_oidc_client_updates_runtime_without_main_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.tests.runtime_auth_helpers import install_oidc_client

    client = object()
    main_module = SimpleNamespace(
        RUNTIME=SimpleNamespace(oidc_client=object()),
    )

    installed = install_oidc_client(monkeypatch, main_module, client)

    assert installed is client
    assert main_module.RUNTIME.oidc_client is client
    assert not hasattr(main_module, "OIDC")


def test_install_oidc_config_updates_runtime_without_main_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.tests.runtime_auth_helpers import install_oidc_config

    config = object()
    main_module = SimpleNamespace(
        RUNTIME=SimpleNamespace(oidc_config=object()),
    )

    installed = install_oidc_config(monkeypatch, main_module, config)

    assert installed is config
    assert main_module.RUNTIME.oidc_config is config
    assert not hasattr(main_module, "OIDC_CFG")


def test_install_cli_token_store_updates_runtime_without_main_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.tests.runtime_auth_helpers import install_cli_token_store

    store = object()
    main_module = SimpleNamespace(
        RUNTIME=SimpleNamespace(cli_token_store=object()),
    )

    installed = install_cli_token_store(monkeypatch, main_module, store)

    assert installed is store
    assert main_module.RUNTIME.cli_token_store is store
    assert not hasattr(main_module, "CLI_TOKEN_STORE")
