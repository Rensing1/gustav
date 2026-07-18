"""Teaching course routes.

Why:
    Course endpoints are a stable authoring surface and should not delegate
    through the large `teaching.py` adapter. This module owns HTTP behavior for
    listing, creating, reading, updating and deleting courses.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from backend.teaching.errors import TeachingRepositoryUnavailable
from backend.web.routes import teaching_guards
from backend.web.routes.teaching import _get_repo, _mark_recently_deleted
from backend.web.routes.teaching_payloads import CourseCreate, CourseUpdate
from backend.web.routes.teaching_serialization import _serialize_course
from backend.web.routes.teaching_shared import (
    _current_sub,
    _is_uuid_like,
    _json_private,
    _private_error,
    _role_in,
)
from backend.web.routes.teaching_validation import clamp_limit_offset as _clamp_limit_offset


teaching_courses_router = APIRouter(tags=["Teaching"])


@teaching_courses_router.get("/api/teaching/courses")
async def list_courses(request: Request, limit: int = 10, offset: int = 0):
    """
    List courses for the current user with simple pagination.

    Behavior:
        - Teachers: return owned courses.
        - Students: return courses the student is a member of.
    """

    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    limit, offset = _clamp_limit_offset(limit=limit, offset=offset, default_limit=10, max_limit=50)
    repo = _get_repo()
    if _role_in(user, "teacher"):
        items = repo.list_courses_for_teacher(teacher_id=sub, limit=limit, offset=offset)
    else:
        items = repo.list_courses_for_student(student_id=sub, limit=limit, offset=offset)
    return _json_private([_serialize_course(c) for c in items], status_code=200)


@teaching_courses_router.post("/api/teaching/courses")
async def create_course(request: Request, payload: CourseCreate):
    """Create a new course owned by the calling teacher."""

    user = getattr(request.state, "user", None)
    if not _role_in(user, "teacher"):
        return _private_error({"error": "forbidden"}, status_code=403)
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    sub = _current_sub(user)
    try:
        course = _get_repo().create_course(
            title=payload.title.strip(),
            subject=payload.subject,
            grade_level=payload.grade_level,
            term=payload.term,
            teacher_id=sub,
        )
    except ValueError:
        return _private_error({"error": "bad_request", "detail": "invalid_input"}, status_code=400)
    return _json_private(_serialize_course(course), status_code=201)


@teaching_courses_router.get("/api/teaching/courses/{course_id}")
async def get_course(request: Request, course_id: str):
    """Get a course by id for the owning teacher."""

    repo = _get_repo()
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return _private_error({"error": "forbidden"}, status_code=403)
    if not _is_uuid_like(course_id):
        return _private_error({"error": "bad_request", "detail": "invalid_course_id"}, status_code=400)
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        if isinstance(repo, DBTeachingRepo):
            course = repo.get_course_for_owner(course_id, sub)
        else:
            course = repo.get_course(course_id)
    except TeachingRepositoryUnavailable:
        raise
    except Exception:
        course = repo.get_course(course_id)
    if not course:
        return _private_error({"error": "not_found"}, status_code=404)
    return _json_private(_serialize_course(course), status_code=200)


@teaching_courses_router.patch("/api/teaching/courses/{course_id}")
async def update_course(request: Request, course_id: str, payload: CourseUpdate):
    """Update course metadata of an owned course."""

    repo = _get_repo()
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return _private_error({"error": "forbidden"}, status_code=403)
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    updates = payload.model_dump(mode="python", exclude_unset=True)
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        if isinstance(repo, DBTeachingRepo):
            if not repo.course_exists_for_owner(course_id, sub):
                exists = repo.course_exists(course_id)
                if exists is False:
                    return _private_error({"error": "not_found"}, status_code=404)
                return _private_error({"error": "forbidden"}, status_code=403)
            updated = repo.update_course_owned(course_id, sub, **updates)
        else:
            course = repo.get_course(course_id)
            if not course:
                return _private_error({"error": "not_found"}, status_code=404)
            owner_id = course["teacher_id"] if isinstance(course, dict) else getattr(course, "teacher_id", None)
            if sub != owner_id:
                return _private_error({"error": "forbidden"}, status_code=403)
            updated = repo.update_course(course_id, **updates)
    except ValueError:
        return _private_error({"error": "bad_request", "detail": "invalid_field"}, status_code=400)
    if not updated:
        return _private_error({"error": "forbidden"}, status_code=403)
    return _json_private(_serialize_course(updated), status_code=200, vary_origin=True)


@teaching_courses_router.delete("/api/teaching/courses/{course_id}")
async def delete_course(request: Request, course_id: str):
    """Delete a course and its memberships for the owning teacher."""

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
                exists = repo.course_exists(course_id)
                if exists is False:
                    return JSONResponse({"error": "not_found"}, status_code=404)
                return JSONResponse({"error": "forbidden"}, status_code=403)
            repo.delete_course_owned(course_id, sub)
            _mark_recently_deleted(sub, course_id)
            return Response(status_code=204, headers={"Cache-Control": "private, no-store"})
        course = repo.get_course(course_id)
        if not course:
            return JSONResponse({"error": "not_found"}, status_code=404)
        owner_id = course["teacher_id"] if isinstance(course, dict) else getattr(course, "teacher_id", None)
        if sub != owner_id:
            return JSONResponse({"error": "forbidden"}, status_code=403)
        repo.delete_course(course_id)
        _mark_recently_deleted(sub, course_id)
        return Response(status_code=204, headers={"Cache-Control": "private, no-store"})
    except TeachingRepositoryUnavailable:
        raise
    except Exception:
        return JSONResponse({"error": "forbidden"}, status_code=403)
