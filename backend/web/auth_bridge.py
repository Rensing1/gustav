"""Current-user API using the identity established by authentication middleware."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


@dataclass(frozen=True)
class AuthBridgeDependencies:
    """Current-user adapter's explicit request-context provider."""

    auth_context_from_request: Callable[[Request], tuple[dict[str, object] | None, str]]


def create_auth_bridge_router(deps: AuthBridgeDependencies) -> APIRouter:
    """Expose the authenticated principal without tokens or a second lookup."""

    router = APIRouter(tags=["Auth"])

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
