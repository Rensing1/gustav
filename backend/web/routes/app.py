"""Application-level read-model routes for the new web platform.

Why:
    SvelteKit needs a small shell bootstrap payload that is independent from
    legacy SSR concerns. This router is the first explicit room read-model
    endpoint in the FastAPI adapter.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


app_router = APIRouter(tags=["App"])


def _spaces_for_role(role: str) -> list[str]:
    if role == "student":
        return ["learning"]
    return ["teaching", "diagnostics", "live"]


def _start_target_for_role(role: str) -> str:
    if role == "student":
        return "/learning"
    return "/teaching"


@app_router.get("/api/app/session-bootstrap")
async def get_session_bootstrap(request: Request):
    """Return shell bootstrap data for the current authenticated session."""
    user = getattr(request.state, "user", None)
    if not isinstance(user, dict):
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers={"Cache-Control": "private, no-store"})

    primary_role = str(user.get("role") or "student")
    body = {
        "user": {
            "sub": str(user.get("sub") or ""),
            "name": str(user.get("name") or ""),
            "role": primary_role,
            "roles": [str(role) for role in (user.get("roles") or []) if isinstance(role, str)],
        },
        "start_target": _start_target_for_role(primary_role),
        "spaces": _spaces_for_role(primary_role),
    }
    return JSONResponse(body, headers={"Cache-Control": "private, no-store"})
