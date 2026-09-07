"""Learner home read model; concern-box routes have independent app providers."""

from __future__ import annotations

import importlib
import sys as _sys

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.learning.usecases.courses import ListCoursesInput, ListCoursesUseCase
from backend.web.routes import learning as learning_routes
from backend.web.security.guards import has_role

app_learner_view_router = APIRouter(tags=["App"])


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


def _list_learner_courses(student_sub: str, limit: int, offset: int, scope: str = "current") -> list[dict]:
    return ListCoursesUseCase(learning_routes._get_repo()).execute(  # type: ignore[attr-defined]
        ListCoursesInput(student_sub=student_sub, limit=limit, offset=offset, scope=scope)
    )


@app_learner_view_router.get("/api/learning/views/learner-home")
async def get_learner_home(request: Request, limit: int = 12, offset: int = 0):
    """Return the learner home read-model with the current student's courses."""

    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_role(user, "student"):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

    student_sub = str(user.get("sub") or "")
    current_items = _app_module()._list_learner_courses(student_sub, limit=int(limit or 12), offset=int(offset or 0), scope="current")
    past_items = _app_module()._list_learner_courses(student_sub, limit=int(limit or 12), offset=int(offset or 0), scope="past")

    def project(items: list[dict], *, past: bool) -> list[dict]:
        return [
            {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or ""),
                "href": (
                    f"/learning/courses/{item.get('id')}/archive"
                    if past else f"/learning/courses/{item.get('id')}"
                ),
                "school_year_start": item.get("school_year_start"),
            }
            for item in items
            if isinstance(item, dict)
        ]
    body = {
        "user": _user_payload(user),
        "current_courses": project(current_items, past=False),
        "past_courses": project(past_items, past=True),
    }
    return JSONResponse(body, headers=_private_headers())
