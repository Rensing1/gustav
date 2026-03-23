"""Application-level read-model routes for the new web platform.

Why:
    SvelteKit needs a small shell bootstrap payload that is independent from
    legacy SSR concerns. This router is the first explicit room read-model
    endpoint in the FastAPI adapter.
"""

from __future__ import annotations

import sys
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


app_router = APIRouter(tags=["App"])


def _resolve_active_main(request: Request):
    """Return the loaded main module whose `app` matches the incoming request."""
    candidates = [module for module in (sys.modules.get("main"), sys.modules.get("backend.web.main")) if module]
    for candidate in candidates:
        try:
            if getattr(candidate, "app", None) is getattr(request, "app", None):
                return candidate
        except Exception:
            pass
    return candidates[0] if candidates else None


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
    mod = _resolve_active_main(request)
    if mod is None:  # pragma: no cover - defensive import fallback
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers={"Cache-Control": "private, no-store"})

    session_cookie_name = getattr(mod, "SESSION_COOKIE_NAME", "gustav_session")
    session_id = request.cookies.get(session_cookie_name)
    if not session_id:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers={"Cache-Control": "private, no-store"})

    record = getattr(mod, "SESSION_STORE").get(session_id)
    if not record:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers={"Cache-Control": "private, no-store"})

    primary_role = getattr(mod, "_primary_role")(getattr(record, "roles", []))
    body: dict[str, Any] = {
        "user": {
            "sub": record.sub,
            "name": getattr(record, "name", ""),
            "role": primary_role,
            "roles": getattr(record, "roles", []),
        },
        "start_target": _start_target_for_role(primary_role),
        "spaces": _spaces_for_role(primary_role),
    }
    return JSONResponse(body, headers={"Cache-Control": "private, no-store"})
