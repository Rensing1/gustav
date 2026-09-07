"""Teacher home routes; concern-box routes have independent app providers."""

from __future__ import annotations

import importlib
import sys as _sys

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.web.security.guards import has_any_role

app_teacher_concern_router = APIRouter(tags=["App"])


def _app_module():
    module = _sys.modules.get("backend.web.routes.app")
    if module is None:  # pragma: no cover - defensive import fallback
        module = importlib.import_module("backend.web.routes.app")
    return module


def _current_user(request: Request) -> dict | None:
    return _app_module()._current_user(request)


def _private_headers() -> dict[str, str]:
    return _app_module()._private_headers()


def _user_payload(user: dict) -> dict[str, object]:
    return _app_module()._user_payload(user)


def _teacher_home_workstarter(owner_sub: str) -> dict[str, object]:
    """Build the teacher work starter from owner-scoped read projections.

    The authenticated teacher subject is passed to every repository-backed
    projection. This keeps foreign courses and units outside the response while
    sharing the unit catalog's established activity ordering.
    """
    app_routes = _app_module()
    courses = app_routes._list_teacher_courses(owner_sub, limit=200, offset=0)
    courses.sort(key=lambda item: str(item.get("title") or "").casefold())
    catalog = app_routes._teacher_units_catalog(owner_sub, query="", sort="updated_desc")
    recent_units = [
        {
            "id": str(item.get("id") or ""),
            "title": str(item.get("title") or ""),
            "updated_at": str(item.get("updated_at") or ""),
            "href": str(item.get("href") or ""),
        }
        for item in list(catalog.get("items") or [])[:3]
        if isinstance(item, dict) and str(item.get("id") or "")
    ]
    return {"courses": courses, "recent_units": recent_units}


@app_teacher_concern_router.get("/api/teaching/views/teacher-home")
async def get_teacher_home(request: Request):
    """Return owner-scoped choices for teaching live or continuing authoring."""

    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

    workstarter = _app_module()._teacher_home_workstarter(str(user.get("sub") or ""))
    return JSONResponse(
        {
            "user": _user_payload(user),
            **workstarter,
            "units_href": "/teaching/units",
            "create_unit_href": "/teaching/units?create=1",
        },
        headers=_private_headers(),
    )
