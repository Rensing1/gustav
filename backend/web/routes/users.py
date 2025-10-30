"""
Users (Directory) API routes — search endpoint for adding course members.

Why:
    Allow teachers/admins to search students by display name, returning stable
    identifiers (sub) and names. The actual directory (IdP) is abstracted behind
    `search_users_by_name` so tests can mock it.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from typing import Dict
from identity_access.domain import ALLOWED_ROLES


users_router = APIRouter(tags=["Users"])  # explicit path below


def search_users_by_name(*, role: str, q: str, limit: int) -> list[dict]:
    """Directory lookup wrapper for tests; delegates to identity_access.directory in prod."""
    try:
        from identity_access import directory  # type: ignore
        return directory.search_users_by_name(role=role, q=q, limit=limit)
    except Exception:
        return []


def list_users_by_role(*, role: str, limit: int, offset: int) -> list[dict]:
    """List users by role via directory adapter; test/dummy-safe when unavailable.

    Returns: [{ sub, name }]
    """
    try:
        from identity_access import directory  # type: ignore
        if hasattr(directory, "list_users_by_role"):
            return directory.list_users_by_role(role=role, limit=limit, offset=offset)  # type: ignore
        # Fallback: approximate by over-fetching search and slicing (no q)
        data = directory.search_users_by_name(role=role, q="", limit=limit + offset)  # type: ignore
        return data[offset: offset + limit]
    except Exception:
        return []


def _is_teacher_or_admin(user: dict | None) -> bool:
    roles = (user or {}).get("roles") or []
    return isinstance(roles, list) and any(r in ("teacher", "admin") for r in roles)


def _private_no_store() -> dict:
    return {"Cache-Control": "private, no-store"}


@users_router.get("/api/users/search")
async def users_search(request: Request, q: str, role: str, limit: int = 20):
    """Search users by display name — teachers/admins only.

    Why:
        Owner teachers need to look up students by display name to add to courses.

    Validation:
        - `q` min length 2
        - `role` in ALLOWED_ROLES (student, teacher, admin)
        - `limit` in 1..50

    Permissions:
        Caller must have role `teacher` or `admin`.
    """
    user = getattr(request.state, "user", None)
    if not _is_teacher_or_admin(user):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_no_store())
    q = (q or "").strip()
    if len(q) < 2:
        return JSONResponse({"error": "bad_request", "detail": "q_too_short"}, status_code=400, headers=_private_no_store())
    if role not in ALLOWED_ROLES:
        return JSONResponse({"error": "bad_request", "detail": "invalid_role"}, status_code=400, headers=_private_no_store())
    limit = max(1, min(50, int(limit or 20)))
    results = search_users_by_name(role=role, q=q, limit=limit)
    # Defensive: normalize shape
    norm = []
    for it in results or []:
        sub = str(it.get("sub", ""))
        name = str(it.get("name", ""))
        if sub and name:
            norm.append({"sub": sub, "name": name})
    return JSONResponse(norm, headers=_private_no_store())


@users_router.get("/api/users/list")
async def users_list(request: Request, role: str, limit: int = 50, offset: int = 0):
    """List users by role — teachers/admins only.

    Permissions:
        Caller must have role `teacher` or `admin`.
    """
    user = getattr(request.state, "user", None)
    if not _is_teacher_or_admin(user):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_no_store())
    if role not in ALLOWED_ROLES:
        return JSONResponse({"error": "bad_request", "detail": "invalid_role"}, status_code=400, headers=_private_no_store())
    limit = max(1, min(200, int(limit or 50)))
    offset = max(0, int(offset or 0))
    results = list_users_by_role(role=role, limit=limit, offset=offset)
    norm = []
    for it in results or []:
        sub = str(it.get("sub", ""))
        name = str(it.get("name", ""))
        if sub and name:
            norm.append({"sub": sub, "name": name})
    return JSONResponse(norm, headers=_private_no_store())
