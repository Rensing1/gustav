"""Teacher home and concern-box routes for the browser app."""

from __future__ import annotations

import importlib
import sys as _sys

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from backend.web.routes import teaching as teaching_routes
from backend.web.routes import teaching_guards
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


def _teacher_concern_box_scopes(active_scope: str) -> list[dict[str, object]]:
    return [
        {"id": "open", "label": "Offen", "active": active_scope == "open"},
        {"id": "archived", "label": "Archiv", "active": active_scope == "archived"},
    ]


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


@app_teacher_concern_router.get("/api/teaching/views/concern-box")
async def get_teacher_concern_box(request: Request, scope: str = "open"):
    """Return the teacher concern box inbox for owned courses."""

    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

    normalized_scope = "archived" if scope == "archived" else "open"
    owner_sub = str(user.get("sub") or "")
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    raw_entries = repo.list_concern_box_entries_for_teacher(owner_sub, normalized_scope)
    visible_subs = sorted(
        {
            str(item.get("student_sub") or "")
            for item in raw_entries
            if isinstance(item, dict) and not bool(item.get("anonymous")) and str(item.get("student_sub") or "")
        }
    )
    names_by_sub = teaching_routes.resolve_student_names(visible_subs) if visible_subs else {}  # type: ignore[attr-defined]
    body = {
        "user": _user_payload(user),
        "scopes": _app_module()._teacher_concern_box_scopes(normalized_scope),
        "active_scope": normalized_scope,
        "entries": [
            {
                "id": str(item.get("id") or ""),
                "course_id": str(item.get("course_id") or ""),
                "course_title": str(item.get("course_title") or ""),
                "message_text": str(item.get("message_text") or ""),
                "anonymous": bool(item.get("anonymous")),
                "student_name": None
                if bool(item.get("anonymous"))
                else names_by_sub.get(str(item.get("student_sub") or ""), "Unbekannt"),
                "created_at": str(item.get("created_at") or ""),
                "archived_at": item.get("archived_at"),
            }
            for item in raw_entries
            if isinstance(item, dict)
        ],
    }
    return JSONResponse(body, headers=_private_headers())


@app_teacher_concern_router.post("/api/teaching/concern-box/entries/{entry_id}/archive")
async def archive_teacher_concern_box_entry(request: Request, entry_id: str):
    """Archive one concern box entry owned by the current teacher."""

    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())
    if not teaching_routes._is_uuid_like(entry_id):  # type: ignore[attr-defined]
        return JSONResponse({"error": "bad_request", "detail": "invalid_entry_id"}, status_code=400, headers=_private_headers())
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf

    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    updated = repo.archive_concern_box_entry_owned(entry_id, str(user.get("sub") or ""))
    if not updated:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())
    return Response(status_code=204, headers=_private_headers())


@app_teacher_concern_router.post("/api/teaching/concern-box/entries/{entry_id}/restore")
async def restore_teacher_concern_box_entry(request: Request, entry_id: str):
    """Restore one archived concern box entry owned by the current teacher."""

    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())
    if not teaching_routes._is_uuid_like(entry_id):  # type: ignore[attr-defined]
        return JSONResponse({"error": "bad_request", "detail": "invalid_entry_id"}, status_code=400, headers=_private_headers())
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf

    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    updated = repo.restore_concern_box_entry_owned(entry_id, str(user.get("sub") or ""))
    if not updated:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())
    return Response(status_code=204, headers=_private_headers())
