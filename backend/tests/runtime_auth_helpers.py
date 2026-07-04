"""Runtime-first auth helpers for backend tests.

Why:
    Auth tests should install stores and OIDC collaborators through the same
    runtime object that production routes read from. This avoids service-locator
    writes on `backend.web.main` and keeps the app composition surface explicit.
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.identity_access.stores import SessionStore, StateStore


def _runtime_from(main_module: Any) -> Any:
    runtime = getattr(main_module, "RUNTIME", None)
    if runtime is None:
        raise RuntimeError("test auth helpers require main_module.RUNTIME")
    return runtime


def install_session_store(
    monkeypatch: pytest.MonkeyPatch,
    main_module: Any,
    store: SessionStore | None = None,
) -> SessionStore:
    """Install one session store through the app runtime test surface.

    Parameters:
        monkeypatch: Pytest monkeypatch fixture used for automatic cleanup.
        main_module: Imported `main` module or a compatible test stub.
        store: Optional store instance. A fresh in-memory store is created when
            omitted.
    Behavior:
        The runtime store is updated directly. The main module must not receive
        auth dependency aliases as a side effect.
    """

    runtime = _runtime_from(main_module)
    current_store = getattr(runtime, "session_store", None)
    store_factory = current_store.__class__ if current_store is not None else SessionStore
    installed = store or store_factory()
    monkeypatch.setattr(runtime, "session_store", installed, raising=False)
    return installed


def install_state_store(
    monkeypatch: pytest.MonkeyPatch,
    main_module: Any,
    store: StateStore | None = None,
) -> StateStore:
    """Install one OIDC state store through the app runtime test surface."""

    runtime = _runtime_from(main_module)
    current_store = getattr(runtime, "state_store", None)
    store_factory = current_store.__class__ if current_store is not None else StateStore
    installed = store or store_factory()
    monkeypatch.setattr(runtime, "state_store", installed, raising=False)
    return installed


def install_oidc_client(monkeypatch: pytest.MonkeyPatch, main_module: Any, client: Any) -> Any:
    """Install an OIDC client through Runtime."""

    runtime = _runtime_from(main_module)
    monkeypatch.setattr(runtime, "oidc_client", client, raising=False)
    return client


def install_oidc_config(monkeypatch: pytest.MonkeyPatch, main_module: Any, config: Any) -> Any:
    """Install OIDC configuration through Runtime."""

    runtime = _runtime_from(main_module)
    monkeypatch.setattr(runtime, "oidc_config", config, raising=False)
    return config


def install_cli_token_store(monkeypatch: pytest.MonkeyPatch, main_module: Any, store: Any) -> Any:
    """Install CLI token storage through Runtime."""

    runtime = _runtime_from(main_module)
    monkeypatch.setattr(runtime, "cli_token_store", store, raising=False)
    return store
