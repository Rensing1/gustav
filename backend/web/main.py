"GUSTAV web application"
from __future__ import annotations

import logging
import os
import sys as _sys
from collections.abc import Callable, Mapping
from functools import partial
from pathlib import Path

from fastapi import FastAPI

# Auth & OIDC Imports
from backend.identity_access.oidc import OIDCConfig
from backend.identity_access.tokens import (
    BearerTokenVerificationError,
    IDTokenVerificationError,
    verify_bearer_token,
    verify_id_token,
)
from backend.web import auth_runtime
from backend.web.app_composition import (
    bootstrap_runtime_environment,
    create_app_shell,
    mount_static_files,
)
from backend.web.app_composition import (
    running_under_pytest as _running_under_pytest,
)
from backend.web.auth_only_app import create_app_auth_only as _create_app_auth_only
from backend.web.auth_session import SESSION_COOKIE_NAME  # noqa: F401
from backend.web.concern_box_providers import ConcernBoxProviders, create_concern_box_providers
from backend.web.layout_response import render_layout_response
from backend.web.learning_course_providers import (
    LearningCourseProviders,
    create_learning_course_providers,
)
from backend.web.main_auth_wiring import create_main_auth_wiring
from backend.web.main_middleware_wiring import install_main_middlewares
from backend.web.main_router_wiring import include_main_routers
from backend.web.main_storage_wiring import initialize_main_storage
from backend.web.profile_providers import ProfileProviders, create_profile_providers
from backend.web.runtime_config import load_teaching_live_poll_interval_seconds
from backend.web.runtime_errors import install_runtime_error_handlers
from backend.web.teacher_catalog_providers import (
    TeacherCatalogProviders,
    create_teacher_catalog_providers,
)

bootstrap_runtime_environment()

# --- App & Settings Setup -------------------------------------------------------

logger = logging.getLogger("gustav.identity_access")
static_dir = Path(__file__).parent / "static"


def create_app(
    *,
    profile_providers: ProfileProviders | None = None,
    concern_box_providers: ConcernBoxProviders | None = None,
    learning_course_providers: LearningCourseProviders | None = None,
    teacher_catalog_providers: TeacherCatalogProviders | None = None,
    access_token_verifier: Callable[[str, OIDCConfig], Mapping[str, object]] | None = None,
) -> FastAPI:
    """Create the package-oriented FastAPI runtime.

    The factory owns shell creation plus runtime, auth, middleware, storage and
    router composition. Module-level exports below are references to the app
    state so tests and smoke tools can inspect the active runtime without
    rebuilding the dependency graph in `main.py`.

    Explicit providers affect only this app. The optional access-token verifier
    permits isolated adapter tests without bypassing the authentication middleware.
    """

    created_app = create_app_shell()
    created_app.state.main_module = _sys.modules[__name__]
    install_runtime_error_handlers(created_app)
    mount_static_files(created_app, static_dir)
    runtime = auth_runtime.create_auth_runtime(running_under_pytest=_running_under_pytest())
    created_app.state.runtime = runtime
    created_app.state.teacher_catalog_providers = teacher_catalog_providers if teacher_catalog_providers is not None else create_teacher_catalog_providers()
    created_app.state.learning_course_providers = learning_course_providers if learning_course_providers is not None else create_learning_course_providers()
    created_app.state.concern_box_providers = concern_box_providers if concern_box_providers is not None else create_concern_box_providers()
    created_app.state.profile_providers = profile_providers if profile_providers is not None else create_profile_providers(runtime)
    initialize_main_storage()
    auth_wiring = create_main_auth_wiring(
        state_store=lambda: runtime.state_store,
        session_store=lambda: runtime.session_store,
        cli_token_store=lambda: runtime.cli_token_store,
        oidc_client=lambda: runtime.oidc_client,
        oidc_config=lambda: runtime.oidc_config,
        verify_bearer_token=access_token_verifier if access_token_verifier is not None else lambda token, cfg: verify_bearer_token(token=token, cfg=cfg),
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
