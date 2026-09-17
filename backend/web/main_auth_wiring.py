"""Auth dependency wiring for the package-oriented FastAPI entry point."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from fastapi import Request

from backend.web.auth_bridge import AuthBridgeDependencies
from backend.web.auth_middleware import (
    AuthMiddlewareDependencies,
    create_auth_context_resolver,
    default_roles_for_cli_sub,
)


@dataclass(frozen=True)
class MainAuthWiring:
    """Auth dependency graph assembled outside the app entry module.

    Why:
        `main.py` should expose the assembled wiring object, not private
        dependency aliases. Runtime providers keep request-time auth behavior
        aligned with the active app state while construction lives here.
    """

    roles_for_cli_sub: Callable[[str], list[str]]
    auth_middleware_dependencies: AuthMiddlewareDependencies
    auth_context_from_request: Callable[[Request], tuple[dict[str, object] | None, str | None]]
    auth_bridge_dependencies: AuthBridgeDependencies


def create_main_auth_wiring(
    *,
    session_store: Callable[[], Any],
    cli_token_store: Callable[[], Any],
    oidc_config: Callable[[], Any],
    verify_bearer_token: Callable[[str, Any], Mapping[str, object]],
    bearer_token_error_type: type[Exception],
    logger: logging.Logger,
) -> MainAuthWiring:
    """Create auth middleware and bridge dependencies for the main app.

    Permissions:
        Startup-only helper. The returned providers enforce authorization at
        request time through the auth middleware and bridge routes.
    """

    roles_for_cli_sub = default_roles_for_cli_sub
    def bound_roles_for_cli_sub(sub):
        return roles_for_cli_sub(sub, oidc_config=oidc_config, logger=logger)

    auth_middleware_dependencies = AuthMiddlewareDependencies(
        session_store=session_store,
        oidc_config=oidc_config,
        cli_token_store=cli_token_store,
        verify_bearer_token=verify_bearer_token,
        bearer_token_error_type=bearer_token_error_type,
        roles_for_cli_sub=bound_roles_for_cli_sub,
        environment_logger=logger,
    )
    auth_context_from_request = create_auth_context_resolver(auth_middleware_dependencies)
    return MainAuthWiring(
        roles_for_cli_sub=bound_roles_for_cli_sub,
        auth_middleware_dependencies=auth_middleware_dependencies,
        auth_context_from_request=auth_context_from_request,
        auth_bridge_dependencies=AuthBridgeDependencies(
            auth_context_from_request=auth_context_from_request,
        ),
    )
