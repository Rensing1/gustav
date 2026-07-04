"""Middleware composition for the package-oriented FastAPI entry point."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, Request

from backend.web.auth_middleware import AuthMiddlewareDependencies, install_auth_middleware
from backend.web.security.headers import install_security_headers_middleware


def install_main_middlewares(
    app: FastAPI,
    *,
    auth_dependencies: AuthMiddlewareDependencies,
    auth_context_from_request: Callable[[Request], tuple[dict[str, object] | None, str | None]],
    environment_provider: Callable[[], str],
) -> None:
    """Install main app middlewares in the existing runtime order."""

    install_auth_middleware(
        app,
        auth_dependencies,
        auth_context_from_request=auth_context_from_request,
    )
    install_security_headers_middleware(
        app,
        environment_provider=environment_provider,
    )
