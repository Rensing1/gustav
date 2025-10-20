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


users_router = APIRouter(tags=["Users"])  # explicit path below


def search_users_by_name(*, role: str, q: str, limit: int) -> list[dict]:
    """Directory lookup stub. Replace with Keycloak admin integration.

    Tests are expected to monkeypatch this function.
    """
    return []


def _is_teacher_or_admin(user: dict | None) -> bool:
    roles = (user or {}).get("roles") or []
    return isinstance(roles, list) and any(r in ("teacher", "admin") for r in roles)


@users_router.get("/api/users/search")
async def users_search(request: Request, q: str, role: str, limit: int = 20):
    """Search users by display name. Only for teachers/admins.

    Validation:
        - q min length 2
        - role must be one of the allowed roles (student, teacher, admin)
        - limit 1..50
    """
    user = getattr(request.state, "user", None)
    if not _is_teacher_or_admin(user):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    q = (q or "").strip()
    if len(q) < 2:
        return JSONResponse({"error": "bad_request", "detail": "q too short"}, status_code=400)
    if role not in ("student", "teacher", "admin"):
        return JSONResponse({"error": "bad_request", "detail": "invalid role"}, status_code=400)
    limit = max(1, min(50, int(limit or 20)))
    results = search_users_by_name(role=role, q=q, limit=limit)
    # Defensive: normalize shape
    norm = []
    for it in results or []:
        sub = str(it.get("sub", ""))
        name = str(it.get("name", ""))
        if sub and name:
            norm.append({"sub": sub, "name": name})
    return norm

