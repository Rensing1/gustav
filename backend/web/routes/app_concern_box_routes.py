"""Concern-box HTTP adapter: authenticated, private and app-scoped."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.teaching.services.concern_box import ConcernBoxService
from backend.web.concern_box_providers import concern_box_providers
from backend.web.routes.app_session_helpers import current_user as _current_user
from backend.web.routes.app_session_helpers import private_headers as _private_headers
from backend.web.routes.app_session_helpers import user_payload as _user_payload
from backend.web.routes.teaching_guards import _csrf_guard
from backend.web.routes.teaching_shared import _is_uuid_like
from backend.web.security.guards import has_any_role, has_role

# Ordinary def handlers keep all synchronous DB/directory work in the threadpool.
app_concern_box_router = APIRouter(tags=["App"])


class ConcernBoxEntryCreatePayload(BaseModel):
    course_id: str = Field(min_length=1)
    message_text: str = Field(min_length=1)
    anonymous: bool = True


def _service(request: Request) -> ConcernBoxService:
    providers = concern_box_providers(request)
    return ConcernBoxService(providers.repository(), providers.resolve_names)


@app_concern_box_router.get("/api/learning/views/concern-box")
def get_learner_concern_box(request: Request, limit: int = 50, offset: int = 0):
    """Return learner-visible courses for the concern box form."""

    user = _current_user(request)
    if user is None:
        return JSONResponse(
            {"error": "unauthenticated"}, status_code=401, headers=_private_headers()
        )
    if not has_role(user, "student"):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

    courses = _service(request).courses(
        str(user.get("sub") or ""), limit=int(limit or 50), offset=int(offset or 0)
    )
    body = {
        "user": _user_payload(user),
        "courses": courses,
    }
    return JSONResponse(body, headers=_private_headers())


@app_concern_box_router.post("/api/learning/concern-box/entries")
def create_learner_concern_box_entry(request: Request, payload: ConcernBoxEntryCreatePayload):
    """Create one concern box entry for the current learner."""

    user = _current_user(request)
    if user is None:
        return JSONResponse(
            {"error": "unauthenticated"}, status_code=401, headers=_private_headers()
        )
    if not has_role(user, "student"):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())
    csrf = _csrf_guard(request)
    if csrf:
        return csrf

    student_sub = str(user.get("sub") or "")
    if not _is_uuid_like(payload.course_id):
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_course_id"},
            status_code=400,
            headers=_private_headers(),
        )

    try:
        created = _service(request).create(
            course_id=payload.course_id,
            student_sub=student_sub,
            message_text=payload.message_text,
            anonymous=payload.anonymous,
        )
    except ValueError:
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_message_text"},
            status_code=400,
            headers=_private_headers(),
        )

    if created is None:
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())
    return JSONResponse(created, status_code=201, headers=_private_headers())


@app_concern_box_router.get("/api/teaching/views/concern-box")
def get_teacher_concern_box(request: Request, scope: str = "open"):
    """Return the teacher concern box inbox for owned courses."""

    user = _current_user(request)
    if user is None:
        return JSONResponse(
            {"error": "unauthenticated"}, status_code=401, headers=_private_headers()
        )
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

    body = {
        "user": _user_payload(user),
        **_service(request).inbox(str(user.get("sub") or ""), scope),
    }
    return JSONResponse(body, headers=_private_headers())


@app_concern_box_router.post("/api/teaching/concern-box/entries/{entry_id}/archive")
def archive_teacher_concern_box_entry(request: Request, entry_id: str):
    """Archive one concern box entry owned by the current teacher."""

    user = _current_user(request)
    if user is None:
        return JSONResponse(
            {"error": "unauthenticated"}, status_code=401, headers=_private_headers()
        )
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())
    if not _is_uuid_like(entry_id):
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_entry_id"},
            status_code=400,
            headers=_private_headers(),
        )
    csrf = _csrf_guard(request)
    if csrf:
        return csrf

    repo = _service(request).repository
    updated = repo.archive_concern_box_entry_owned(entry_id, str(user.get("sub") or ""))
    if not updated:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())
    return Response(status_code=204, headers=_private_headers())


@app_concern_box_router.post("/api/teaching/concern-box/entries/{entry_id}/restore")
def restore_teacher_concern_box_entry(request: Request, entry_id: str):
    """Restore one archived concern box entry owned by the current teacher."""

    user = _current_user(request)
    if user is None:
        return JSONResponse(
            {"error": "unauthenticated"}, status_code=401, headers=_private_headers()
        )
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())
    if not _is_uuid_like(entry_id):
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_entry_id"},
            status_code=400,
            headers=_private_headers(),
        )
    csrf = _csrf_guard(request)
    if csrf:
        return csrf

    repo = _service(request).repository
    updated = repo.restore_concern_box_entry_owned(entry_id, str(user.get("sub") or ""))
    if not updated:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())
    return Response(status_code=204, headers=_private_headers())
