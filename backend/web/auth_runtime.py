"""Runtime construction helpers for authentication state and stores."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
import os

from backend.identity_access.bff_sessions import BFFSessionStore
from backend.identity_access.cli_tokens import DBCLITokenStore, InMemoryCLITokenStore
from backend.identity_access.oidc import OIDCClient, OIDCConfig
from backend.identity_access.stores import SessionStore, StateStore


class AuthSettings:
    """Small mutable settings facade kept for test overrides.

    Why:
        Tests can override `RUNTIME.settings.environment` through this object.
        Keeping the behavior here lets `main.py` expose one runtime object
        without owning settings parsing.
    """

    def __init__(self) -> None:
        self._env_override: str | None = None

    @property
    def environment(self) -> str:
        if self._env_override is not None:
            return self._env_override
        return os.getenv("GUSTAV_ENV", "dev").lower()

    def override_environment(self, env: str | None) -> None:
        """Override environment for tests, or reset with None."""

        self._env_override = env


@dataclass
class AuthRuntime:
    """Authentication runtime objects shared by the FastAPI adapter.

    Why:
        `main.py` exposes this object on `app.state.runtime`, but construction
        belongs here so the app entry point does not directly own OIDC clients
        or mutable auth stores.
    """

    settings: AuthSettings
    oidc_config: OIDCConfig
    oidc_client: OIDCClient
    state_store: Any
    session_store: Any
    bff_session_store: Any
    cli_token_store: Any


def load_oidc_config(environ: Mapping[str, str] | None = None) -> OIDCConfig:
    """Load OIDC configuration from production-compatible environment names."""

    env = os.environ if environ is None else environ
    base_url = env.get("KC_BASE_URL", "http://localhost:8080")
    realm = env.get("KC_REALM", "gustav")
    client_id = env.get("KC_CLIENT_ID", "gustav-web")
    redirect_uri = env.get("REDIRECT_URI", "https://app.localhost/auth/callback")
    public_base = env.get("KC_PUBLIC_BASE_URL", base_url)
    return OIDCConfig(
        base_url=base_url,
        realm=realm,
        client_id=client_id,
        redirect_uri=redirect_uri,
        public_base_url=public_base,
    )


def create_session_store(
    *,
    running_under_pytest: bool,
    backend: str | None = None,
) -> Any:
    """Create the browser session store with DB backend when configured."""

    selected = (backend or os.getenv("SESSIONS_BACKEND", "memory")).lower()
    if (not running_under_pytest) and selected == "db":
        try:
            from backend.identity_access.stores_db import DBSessionStore

            return DBSessionStore()
        except ImportError:
            return SessionStore()
    return SessionStore()


def create_bff_session_store(
    *,
    running_under_pytest: bool,
    backend: str | None = None,
) -> Any:
    """Create the BFF session store with DB backend when configured."""

    selected = (backend or os.getenv("SESSIONS_BACKEND", "memory")).lower()
    if (not running_under_pytest) and selected == "db":
        try:
            from backend.identity_access.bff_sessions_db import DBBFFSessionStore

            return DBBFFSessionStore()
        except ImportError:
            return BFFSessionStore()
    return BFFSessionStore()


def build_cli_token_store(
    *,
    running_under_pytest: bool,
    backend: str | None = None,
    db_cli_token_store: Callable[[], Any] = DBCLITokenStore,
    memory_cli_token_store: Callable[[], Any] = InMemoryCLITokenStore,
) -> Any:
    """Create the CLI token store and fail fast on unsupported backends.

    CLI tokens are bearer credentials for write-capable authoring actions. A
    silent fallback from DB to memory would make existing tokens unusable after
    a restart and could hide a broken production deployment.
    """

    selected = (backend or os.getenv("CLI_TOKENS_BACKEND", os.getenv("SESSIONS_BACKEND", "memory"))).lower()
    if running_under_pytest and "CLI_TOKENS_BACKEND" not in os.environ and backend is None:
        return memory_cli_token_store()
    if selected == "db":
        return db_cli_token_store()
    if selected == "memory":
        return memory_cli_token_store()
    raise RuntimeError(f"Unsupported CLI_TOKENS_BACKEND: {selected}")


def create_auth_runtime(*, running_under_pytest: bool) -> AuthRuntime:
    """Create the default authentication runtime for the FastAPI app.

    Permissions:
        Startup-only helper. Callers should expose only the specific stores or
        dependency providers needed by route and middleware wiring.
    """

    oidc_config = load_oidc_config()
    return AuthRuntime(
        settings=AuthSettings(),
        oidc_config=oidc_config,
        oidc_client=OIDCClient(oidc_config),
        state_store=StateStore(),
        session_store=create_session_store(running_under_pytest=running_under_pytest),
        bff_session_store=create_bff_session_store(running_under_pytest=running_under_pytest),
        cli_token_store=build_cli_token_store(running_under_pytest=running_under_pytest),
    )
