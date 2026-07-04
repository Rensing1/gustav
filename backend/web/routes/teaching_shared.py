"""Small shared helpers for Teaching route adapters.

Why:
    Teaching routes are being split into focused modules. Tiny response,
    identity, and UUID helpers should be imported explicitly instead of being
    hidden behind the large `teaching.py` module.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse


def _role_in(user: dict | None, role: str) -> bool:
    """Return whether the authenticated user has a specific role."""

    if not user:
        return False
    roles = user.get("roles") or []
    if not isinstance(roles, list):
        return False
    return role in roles


def _current_sub(user: dict | None) -> str:
    """Return the current user's subject identifier, or an empty string."""

    if not user:
        return ""
    sub = user.get("sub")
    return str(sub) if sub else ""


def _json_private(payload, *, status_code: int = 200, vary_origin: bool = False) -> JSONResponse:
    """Return JSON with cache disabled for shared caches and browsers."""

    headers = {"Cache-Control": "private, no-store"}
    if vary_origin:
        headers["Vary"] = "Origin"
    return JSONResponse(content=payload, status_code=status_code, headers=headers)


def _private_error(payload: dict, *, status_code: int, vary_origin: bool = False) -> JSONResponse:
    """Return private error JSON to avoid leaking scoped metadata through caches."""

    headers = {"Cache-Control": "private, no-store"}
    if vary_origin:
        headers["Vary"] = "Origin"
    return JSONResponse(content=payload, status_code=status_code, headers=headers)


def _require_teacher(request: Request):
    """Return (user, error_response) ensuring caller has teacher role."""

    user = getattr(request.state, "user", None)
    if not _role_in(user, "teacher"):
        return None, _private_error({"error": "forbidden"}, status_code=403)
    return user, None


def _is_uuid_like(value: str) -> bool:
    """Best-effort UUID format check without coercing FastAPI to return 422."""

    try:
        UUID(str(value))
    except (ValueError, TypeError):
        return False
    return True
