"""Authentication middleware and request auth-context resolution."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlparse
import hmac
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from backend.identity_access.domain import ALLOWED_ROLES
from backend.web.auth_claims import primary_role, user_context_from_claims
from backend.web.auth_flow import auth_failure_path_class, auth_failure_reason, requires_bff_bearer_auth
from backend.web.auth_session import SESSION_COOKIE_NAME
from backend.web.cli_authoring import cli_capability_for_request
from backend.web.legacy_retirement import retired_legacy_product_response
from backend.web.routes.redirects import safe_inapp_path


@dataclass
class AuthMiddlewareDependencies:
    """Runtime providers needed by the authentication middleware.

    Provider callables keep runtime wiring explicit while the middleware
    behavior itself lives outside the app entry module. Tests may replace a
    provider on this object when they need to isolate the middleware from an
    external identity provider.
    """

    session_store: Callable[[], Any]
    cli_token_store: Callable[[], Any]
    oidc_config: Callable[[], Any]
    verify_bearer_token: Callable[[str, Any], Mapping[str, object]]
    bearer_token_error_type: type[Exception]
    roles_for_cli_sub: Callable[[str], list[str]]
    internal_bff_secret: Callable[[], str]
    environment_logger: logging.Logger


def build_login_url_with_return_to(path: str | None) -> str:
    """Build a login URL with a safe optional return path."""

    safe = safe_inapp_path(path)
    if not safe:
        return "/auth/login"
    return f"/auth/login?{urlencode({'redirect': safe})}"


def is_public_path(path: str) -> bool:
    """Return whether a path is intentionally reachable without auth."""

    return path.startswith(("/auth/", "/static/")) or path in (
        "/health",
        "/favicon.ico",
    )


def default_roles_for_cli_sub(
    sub: str,
    *,
    oidc_config: Callable[[], Any],
    logger: logging.Logger,
) -> list[str]:
    """Load current roles for a CLI-authenticated user.

    The default is fail-closed when roles cannot be loaded. Tests may monkeypatch
    the main module's compatibility alias to keep middleware behavior isolated
    from Keycloak.
    """

    try:
        from backend.identity_access.admin_client import AdminClient

        roles = AdminClient(oidc_config()).get_realm_roles(user_id=sub)
    except Exception as exc:
        logger.warning("CLI role lookup failed reason=role_lookup_failed err=%s", exc.__class__.__name__)
        return []
    return [role for role in roles if role in ALLOWED_ROLES]


def _has_valid_internal_bff_secret(request: Request, deps: AuthMiddlewareDependencies) -> bool:
    expected = str(deps.internal_bff_secret() or "").strip()
    provided = str(request.headers.get("x-gustav-internal-secret") or "").strip()
    return bool(expected) and bool(provided) and hmac.compare_digest(provided, expected)


def _bearer_token_from_authorization_header(request: Request) -> str | None:
    raw = request.headers.get("authorization") or ""
    prefix = "Bearer "
    if not raw.startswith(prefix):
        return None
    token = raw[len(prefix):].strip()
    return token or None


def create_auth_context_resolver(
    deps: AuthMiddlewareDependencies,
) -> Callable[[Request], tuple[dict[str, object] | None, str]]:
    """Create the auth-context resolver used by middleware and `/api/me`.

    Behavior:
        - CLI bearer tokens are accepted only on CLI-enabled authoring routes.
        - JWT bearer tokens are verified against the configured OIDC settings.
        - Browser sessions are used only when the path does not require BFF
          bearer authentication.

    Permissions:
        Callers receive only compact server-side auth context. This resolver
        does not expose raw tokens to templates or clients.
    """

    def _cli_bearer_auth_context_from_token(
        token: str,
        *,
        request: Request,
        required_scope: str,
    ) -> dict[str, object] | None:
        try:
            record = deps.cli_token_store().verify_token(token, required_scope=required_scope)
        except Exception as exc:
            deps.environment_logger.warning("CLI token verification failed: %s", exc.__class__.__name__)
            return None
        if record is None:
            return None
        roles = deps.roles_for_cli_sub(record.user_sub)
        if not roles:
            return None
        return {
            "user": {
                "sub": record.user_sub,
                "name": "CLI",
                "role": primary_role(roles),
                "roles": roles,
            },
            "expires_at": record.expires_at,
            "id_token": None,
            "cli_token_id": record.id,
        }

    def _bearer_auth_context_from_request(request: Request) -> tuple[bool, dict[str, object] | None]:
        token = _bearer_token_from_authorization_header(request)
        if not token:
            return False, None
        if token.startswith("gustav_cli_"):
            capability = cli_capability_for_request(request.method, request.url.path)
            if capability is None:
                return True, None
            return True, _cli_bearer_auth_context_from_token(
                token,
                request=request,
                required_scope=capability.required_scope,
            )
        try:
            claims = deps.verify_bearer_token(token, deps.oidc_config())
        except deps.bearer_token_error_type as exc:
            deps.environment_logger.warning("Bearer token verification failed: %s", getattr(exc, "code", exc.__class__.__name__))
            return True, None
        exp = claims.get("exp")
        expires_at = int(exp) if isinstance(exp, (int, float)) else None
        return True, {"user": user_context_from_claims(claims), "expires_at": expires_at, "id_token": None}

    def _session_auth_context_from_request(request: Request) -> dict[str, object] | None:
        sid = request.cookies.get(SESSION_COOKIE_NAME)
        if sid:
            try:
                rec = deps.session_store().get(sid)
            except Exception as exc:
                deps.environment_logger.warning("Session store get failed: %s", exc.__class__.__name__)
                rec = None
        else:
            rec = None
        if not rec:
            return None
        return {
            "session_id": sid,
            "session_record": rec,
            "user": {"sub": rec.sub, "name": getattr(rec, "name", ""), "role": primary_role(rec.roles), "roles": rec.roles},
            "expires_at": rec.expires_at,
            "id_token": getattr(rec, "id_token", None),
        }

    def auth_context_from_request(request: Request) -> tuple[dict[str, object] | None, str]:
        bearer_attempted, bearer_context = _bearer_auth_context_from_request(request)
        if bearer_attempted:
            return bearer_context, "bearer"
        if requires_bff_bearer_auth(request.url.path):
            return None, "missing_bearer"
        return _session_auth_context_from_request(request), "session"

    return auth_context_from_request


def install_auth_middleware(
    app: FastAPI,
    deps: AuthMiddlewareDependencies,
    *,
    auth_context_from_request: Callable[[Request], tuple[dict[str, object] | None, str]] | None = None,
) -> None:
    """Install GUSTAV's authentication middleware on the FastAPI app."""

    resolver = auth_context_from_request or create_auth_context_resolver(deps)

    @app.middleware("http")
    async def auth_enforcement(request: Request, call_next):
        path = request.url.path
        if is_public_path(path):
            return await call_next(request)
        if path.startswith("/backend-internal/") and _has_valid_internal_bff_secret(request, deps):
            return await call_next(request)

        auth_context, auth_source = resolver(request)

        if not auth_context:
            if path.startswith("/api/") or path.startswith("/internal/") or path.startswith("/backend-internal/"):
                deps.environment_logger.info(
                    "auth_failure reason=%s path_class=%s",
                    auth_failure_reason(auth_source),
                    auth_failure_path_class(path),
                )
                headers = {"Cache-Control": "private, no-store", "Vary": "Origin"}
                return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=headers)
            if "HX-Request" in request.headers:
                return_to = None
                hx_current = request.headers.get("HX-Current-URL")
                if hx_current:
                    try:
                        return_to = urlparse(hx_current).path
                    except Exception:
                        return_to = None
                login_url = build_login_url_with_return_to(return_to or path)
                return Response(
                    status_code=401,
                    headers={"HX-Redirect": login_url, "Cache-Control": "private, no-store", "Vary": "HX-Request"},
                )

            return_to = path if request.method in ("GET", "HEAD") else None
            if return_to is None:
                referer = request.headers.get("referer")
                if referer:
                    try:
                        return_to = urlparse(referer).path
                    except Exception:
                        return_to = None
            login_url = build_login_url_with_return_to(return_to)
            return RedirectResponse(url=login_url, status_code=302, headers={"Cache-Control": "private, no-store"})

        request.state.user = auth_context["user"]
        request.state.auth_source = auth_source
        request.state.auth_expires_at = auth_context.get("expires_at")
        if auth_context.get("cli_token_id"):
            request.state.cli_token_id = auth_context.get("cli_token_id")
        try:
            request.state.id_token = auth_context.get("id_token")
        except Exception:
            request.state.id_token = None

        legacy_response = retired_legacy_product_response(request, auth_context["user"])
        if legacy_response is not None:
            return legacy_response
        return await call_next(request)
