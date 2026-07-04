"""Auth bridge routes for OIDC callback and current-user API."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from backend.web.auth_claims import display_name_from_claims, roles_from_claims
from backend.web.auth_session import app_session_ttl_seconds, set_session_cookie


@dataclass(frozen=True)
class AuthBridgeDependencies:
    """Runtime providers needed by the auth bridge routes.

    Why:
        Existing tests monkeypatch the main module's OIDC and session globals.
        Provider callables keep those patches effective without keeping route
        implementations in the app entry module.
    """

    state_store: Callable[[], Any]
    session_store: Callable[[], Any]
    oidc_client: Callable[[], Any]
    oidc_config: Callable[[], Any]
    verify_id_token: Callable[[str, Any], Mapping[str, object]]
    id_token_error_type: type[Exception]
    environment: Callable[[], str]
    auth_context_from_request: Callable[[Request], tuple[dict[str, object] | None, str]]
    logger: logging.Logger


def create_auth_bridge_router(deps: AuthBridgeDependencies) -> APIRouter:
    """Create auth bridge routes without owning app-level auth state.

    Behavior:
        - `GET /auth/callback` completes the OIDC code flow and creates the
          opaque GUSTAV app session.
        - `GET /api/me` exposes the authenticated principal DTO used by the
          frontend and BFF bridge.

    Permissions:
        `/auth/callback` is public but requires a valid server-side state.
        `/api/me` returns 401 when no bearer or session auth context exists.
    """

    router = APIRouter(tags=["Auth"])

    @router.get("/auth/callback")
    async def auth_callback(request: Request, code: str | None = None, state: str | None = None):
        error_headers = {"Cache-Control": "private, no-store"}
        if not code or not state:
            return JSONResponse({"error": "invalid_code_or_state"}, status_code=400, headers=error_headers)
        rec = deps.state_store().pop_valid(state)
        if not rec:
            return JSONResponse({"error": "invalid_code_or_state"}, status_code=400, headers=error_headers)
        try:
            tokens = deps.oidc_client().exchange_code_for_tokens(code=code, code_verifier=rec.code_verifier)
        except Exception as exc:
            deps.logger.warning("Token exchange failed: %s", exc.__class__.__name__)
            return JSONResponse({"error": "token_exchange_failed"}, status_code=400, headers=error_headers)
        id_token = tokens.get("id_token")
        if not id_token or not isinstance(id_token, str):
            return JSONResponse({"error": "invalid_id_token"}, status_code=400, headers=error_headers)
        try:
            claims = deps.verify_id_token(id_token, deps.oidc_config())
        except deps.id_token_error_type as exc:
            deps.logger.warning("ID token verification failed: %s", getattr(exc, "code", exc.__class__.__name__))
            return JSONResponse({"error": "invalid_id_token"}, status_code=400, headers=error_headers)
        claim_nonce = claims.get("nonce")
        if getattr(rec, "nonce", None) and claim_nonce != rec.nonce:
            return JSONResponse({"error": "invalid_nonce"}, status_code=400, headers=error_headers)

        roles = roles_from_claims(claims)
        display_name = display_name_from_claims(claims)
        sess = deps.session_store().create(
            sub=str(claims.get("sub") or "unknown-sub"),
            roles=roles,
            name=str(display_name),
            ttl_seconds=app_session_ttl_seconds(),
            id_token=id_token,
        )
        dest = rec.redirect or "/"
        resp = RedirectResponse(url=dest, status_code=302)
        resp.headers["Cache-Control"] = "private, no-store"
        max_age = sess.ttl_seconds if deps.environment() == "prod" else None
        set_session_cookie(resp, sess.session_id, environment=deps.environment(), max_age=max_age)
        return resp

    @router.get("/api/me")
    async def get_me(request: Request):
        user = getattr(request.state, "user", None)
        if not isinstance(user, dict):
            auth_context, _auth_source = deps.auth_context_from_request(request)
            if not auth_context:
                return JSONResponse(
                    {"error": "unauthenticated"},
                    status_code=401,
                    headers={"Cache-Control": "private, no-store"},
                )
            user = auth_context["user"]
            expires_at_raw = auth_context.get("expires_at")
        else:
            expires_at_raw = getattr(request.state, "auth_expires_at", None)

        if not isinstance(user, dict):
            return JSONResponse(
                {"error": "unauthenticated"},
                status_code=401,
                headers={"Cache-Control": "private, no-store"},
            )

        exp_iso = (
            datetime.fromtimestamp(int(expires_at_raw), tz=timezone.utc).isoformat(timespec="seconds")
            if isinstance(expires_at_raw, (int, float))
            else None
        )
        return JSONResponse(
            {
                "sub": str(user.get("sub") or ""),
                "roles": [str(role) for role in (user.get("roles") or []) if isinstance(role, str)],
                "name": str(user.get("name") or ""),
                "expires_at": exp_iso,
            },
            headers={"Cache-Control": "private, no-store"},
        )

    return router
