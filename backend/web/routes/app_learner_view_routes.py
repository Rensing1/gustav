"""Learner read-model and concern-box routes for the browser app."""

from __future__ import annotations

import importlib
import sys as _sys

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.learning.usecases.courses import ListCoursesInput, ListCoursesUseCase
from backend.web.routes import learning as learning_routes
from backend.web.routes import teaching as teaching_routes
from backend.web.routes import teaching_guards
from backend.web.security.guards import has_role


app_learner_view_router = APIRouter(tags=["App"])


class ConcernBoxEntryCreatePayload(BaseModel):
    course_id: str = Field(min_length=1)
    message_text: str = Field(min_length=1)
    anonymous: bool = True


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


def _field_value(item: object, key: str) -> object:
    return _app_module()._field_value(item, key)


def _list_learner_courses(student_sub: str, limit: int, offset: int, scope: str = "current") -> list[dict]:
    return ListCoursesUseCase(learning_routes._get_repo()).execute(  # type: ignore[attr-defined]
        ListCoursesInput(student_sub=student_sub, limit=limit, offset=offset, scope=scope)
    )


def _list_concern_box_courses_for_student(student_sub: str, limit: int, offset: int) -> list[dict]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    return [
        {
            "id": str(_field_value(item, "id") or ""),
            "title": str(_field_value(item, "title") or ""),
        }
        for item in (repo.list_courses_for_student(student_id=student_sub, limit=limit, offset=offset) or [])
        if str(_field_value(item, "id") or "")
    ]


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


@app_learner_view_router.get("/api/learning/views/concern-box")
async def get_learner_concern_box(request: Request, limit: int = 50, offset: int = 0):
    """Return learner-visible courses for the concern box form."""

    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_role(user, "student"):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

    courses = _app_module()._list_concern_box_courses_for_student(
        str(user.get("sub") or ""), limit=int(limit or 50), offset=int(offset or 0)
    )
    body = {
        "user": _user_payload(user),
        "courses": courses,
    }
    return JSONResponse(body, headers=_private_headers())


@app_learner_view_router.post("/api/learning/concern-box/entries")
async def create_learner_concern_box_entry(request: Request, payload: ConcernBoxEntryCreatePayload):
    """Create one concern box entry for the current learner."""

    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_role(user, "student"):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf

    student_sub = str(user.get("sub") or "")
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    if not teaching_routes._is_uuid_like(payload.course_id):  # type: ignore[attr-defined]
        return JSONResponse({"error": "bad_request", "detail": "invalid_course_id"}, status_code=400, headers=_private_headers())
    if not repo.student_has_course(payload.course_id, student_sub):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

    try:
        created = repo.create_concern_box_entry(
            course_id=payload.course_id,
            student_sub=student_sub,
            message_text=payload.message_text,
            anonymous=payload.anonymous,
        )
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_message_text"}, status_code=400, headers=_private_headers())

    if created is None:
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())
    return JSONResponse(created, status_code=201, headers=_private_headers())
