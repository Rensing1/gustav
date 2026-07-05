"""Teaching course-member routes.

Why:
    Course membership is a small course-owned surface. Keeping its HTTP adapter
    here removes another direct dependency on the large `teaching.py` module.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from backend.web.routes import teaching_guards
from backend.web.routes.teaching import (
    _get_repo,
    _resolve_student_names_runtime,
    _resp_non_owner_or_unknown,
    _teacher_id_of,
)
from backend.web.routes.teaching_payloads import AddMember
from backend.web.routes.teaching_shared import _current_sub, _json_private, _private_error, _role_in
from backend.web.routes.teaching_validation import clamp_limit_offset as _clamp_limit_offset


teaching_course_members_router = APIRouter(tags=["Teaching"])
logger = logging.getLogger("gustav.web.teaching.course_members")


@teaching_course_members_router.get("/api/teaching/courses/{course_id}/members")
async def list_members(request: Request, course_id: str, limit: int = 10, offset: int = 0):
    """List members for a course owned by the current teacher."""

    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return _private_error({"error": "forbidden"}, status_code=403)
    limit, offset = _clamp_limit_offset(limit=limit, offset=offset, default_limit=10, max_limit=50)
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        repo = _get_repo()
        if isinstance(repo, DBTeachingRepo):
            if not repo.course_exists_for_owner(course_id, sub):
                return _resp_non_owner_or_unknown(course_id, sub)
            pairs = repo.list_members_for_owner(course_id, sub, limit=limit, offset=offset)
        else:
            course = repo.get_course(course_id)
            if not course:
                return _private_error({"error": "not_found"}, status_code=404)
            if _teacher_id_of(course) != sub:
                return _private_error({"error": "forbidden"}, status_code=403)
            pairs = repo.list_members(course_id, limit=limit, offset=offset)
    except Exception as exc:
        cid_tail = (course_id or "").replace("-", "")[-6:]
        logger.warning("list_members failed: cid_tail=%s err=%s", cid_tail, exc.__class__.__name__)
        return _private_error({"error": "forbidden"}, status_code=403)

    subs = [sid for sid, _ in pairs]
    names = await asyncio.to_thread(_resolve_student_names_runtime, subs)
    result = [{"sub": sid, "name": names.get(sid, sid), "joined_at": joined_at} for sid, joined_at in pairs]
    return _json_private(result, status_code=200)


@teaching_course_members_router.post("/api/teaching/courses/{course_id}/members")
async def add_member(request: Request, course_id: str, payload: AddMember):
    """Add a student member to a course owned by the caller."""

    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return _private_error({"error": "forbidden"}, status_code=403)
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    student_sub = getattr(payload, "student_sub", None) or getattr(payload, "sub", None)
    if not isinstance(student_sub, str) or not student_sub.strip():
        return _private_error({"error": "bad_request", "detail": "student_sub_required"}, status_code=400)
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        repo = _get_repo()
        if isinstance(repo, DBTeachingRepo):
            if not repo.course_exists_for_owner(course_id, sub):
                return _resp_non_owner_or_unknown(course_id, sub)
            created = repo.add_member_owned(course_id, sub, student_sub.strip())
        else:
            course = repo.get_course(course_id)
            if not course:
                return _private_error({"error": "not_found"}, status_code=404)
            if _teacher_id_of(course) != sub:
                return _private_error({"error": "forbidden"}, status_code=403)
            created = repo.add_member(course_id, student_sub.strip())
    except Exception:
        return _resp_non_owner_or_unknown(course_id, sub)
    if created:
        return _json_private({}, status_code=201)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@teaching_course_members_router.delete("/api/teaching/courses/{course_id}/members/{student_sub}")
async def remove_member(request: Request, course_id: str, student_sub: str):
    """Remove a student member from a course owned by the caller."""

    repo = _get_repo()
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        if isinstance(repo, DBTeachingRepo):
            if not repo.course_exists_for_owner(course_id, sub):
                return _resp_non_owner_or_unknown(course_id, sub)
            repo.remove_member_owned(course_id, sub, str(student_sub))
        else:
            course = repo.get_course(course_id)
            if not course:
                return JSONResponse({"error": "not_found"}, status_code=404)
            if _teacher_id_of(course) != sub:
                return JSONResponse({"error": "forbidden"}, status_code=403)
            repo.remove_member(course_id, str(student_sub))
    except Exception:
        return _resp_non_owner_or_unknown(course_id, sub)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})
