"GUSTAV alpha-2"
from __future__ import annotations

from functools import partial
from pathlib import Path
import os
import logging

from fastapi import FastAPI

# Auth & OIDC Imports
from backend.identity_access.tokens import BearerTokenVerificationError, IDTokenVerificationError, verify_bearer_token, verify_id_token
import sys as _sys

from backend.web.auth_session import SESSION_COOKIE_NAME
from backend.web import auth_runtime
from backend.web.app_composition import (
    bootstrap_runtime_environment,
    create_app_shell,
    mount_static_files,
    running_under_pytest as _running_under_pytest,
)
from backend.web.runtime_config import load_teaching_live_poll_interval_seconds
from backend.web.auth_only_app import create_app_auth_only as _create_app_auth_only
from backend.web.layout_response import render_layout_response
from backend.web.main_auth_wiring import create_main_auth_wiring
from backend.web.main_middleware_wiring import install_main_middlewares
from backend.web.main_router_wiring import include_main_routers
from backend.web.main_storage_wiring import initialize_main_storage

# Ensure legacy imports consistently reference the same module instance.
if __name__ == "backend.web.main":
    _sys.modules.setdefault("main", _sys.modules[__name__])


bootstrap_runtime_environment()

# --- App & Settings Setup -------------------------------------------------------

logger = logging.getLogger("gustav.identity_access")
static_dir = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    """Create the package-oriented FastAPI runtime.

    The factory owns shell creation plus runtime, auth, middleware, storage and
    router composition. Module-level exports below are references to the app
    state so tests and smoke tools can inspect the active runtime without
    rebuilding the dependency graph in `main.py`.
    """

    created_app = create_app_shell()
    created_app.state.main_module = _sys.modules[__name__]
    mount_static_files(created_app, static_dir)
    runtime = auth_runtime.create_auth_runtime(running_under_pytest=_running_under_pytest())
    created_app.state.runtime = runtime
    initialize_main_storage()
    auth_wiring = create_main_auth_wiring(
        state_store=lambda: runtime.state_store,
        session_store=lambda: runtime.session_store,
        cli_token_store=lambda: runtime.cli_token_store,
        oidc_client=lambda: runtime.oidc_client,
        oidc_config=lambda: runtime.oidc_config,
        verify_bearer_token=lambda token, cfg: verify_bearer_token(token=token, cfg=cfg),
        bearer_token_error_type=BearerTokenVerificationError,
        verify_id_token=lambda id_token, cfg: verify_id_token(id_token=id_token, cfg=cfg),
        id_token_error_type=IDTokenVerificationError,
        internal_bff_secret=lambda: os.getenv("BFF_INTERNAL_SHARED_SECRET", ""),
        environment=lambda: runtime.settings.environment,
        logger=logger,
    )
    created_app.state.auth_wiring = auth_wiring
    install_main_middlewares(
        created_app,
        auth_dependencies=auth_wiring.auth_middleware_dependencies,
        auth_context_from_request=auth_wiring.auth_context_from_request,
        environment_provider=lambda: runtime.settings.environment,
    )
    include_main_routers(
        created_app,
        layout_response=render_layout_response,
        auth_bridge_dependencies=auth_wiring.auth_bridge_dependencies,
    )
    return created_app


app = create_app()
RUNTIME = app.state.runtime
AUTH_WIRING = app.state.auth_wiring

# Polling configuration for Teaching Live UI (seconds).
# Derived from environment so ops can tune the interval without code
# changes. Tests may override this constant directly on the main module.
TEACHING_LIVE_POLL_INTERVAL_SECONDS = load_teaching_live_poll_interval_seconds()


create_app_auth_only = partial(_create_app_auth_only, environment_provider=lambda: RUNTIME.settings.environment)
