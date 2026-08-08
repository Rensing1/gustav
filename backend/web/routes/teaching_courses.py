"""Teaching course routes.

Why:
    Course endpoints are a stable authoring surface and should not delegate
    through the large `teaching.py` adapter. This module owns HTTP behavior for
    listing, creating, reading, updating and deleting courses.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request

from backend.teaching.errors import TeachingRepositoryUnavailable
from backend.web.routes import teaching_guards
from backend.web.routes.teaching import _get_repo
from backend.web.routes.teaching_payloads import CourseArchiveBatchPayload, CourseCreate, CourseDeletionPayload, CourseUpdate
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
async def list_courses(
    request: Request,
    limit: int = 10,
    offset: int = 0,
    status: Literal["active", "archived"] = "active",
):
    """
    List courses for the current user with simple pagination.

    Behavior:
        - Teachers: return owned active or archived courses.
        - Students: return active courses the student is a member of.

    Permissions:
        Requesting archived courses requires the teacher role. Ownership is
        enforced by the repository under the caller's database identity.
    """

    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    limit, offset = _clamp_limit_offset(limit=limit, offset=offset, default_limit=10, max_limit=50)
    repo = _get_repo()
    if _role_in(user, "teacher"):
        items = repo.list_course_catalog_for_owner(
            owner_sub=sub,
            status=status,
            query="",
            school_year_start=None,
            subject="",
            limit=limit,
            offset=offset,
        )
    else:
        if status != "active":
            return _private_error({"error": "forbidden"}, status_code=403)
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
    if not payload.title.strip():
        return _private_error({"error": "bad_request", "detail": "invalid_input"}, status_code=400)
    if payload.subject is None or payload.grade_level is None or payload.school_year_start is None:
        return _private_error(
            {"error": "bad_request", "detail": "course_metadata_incomplete"},
            status_code=400,
        )
    sub = _current_sub(user)
    try:
        course = _get_repo().create_course(
            title=payload.title.strip(),
            subject=payload.subject,
            grade_level=payload.grade_level,
            term=payload.term,
            school_year_start=payload.school_year_start,
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
    if str(_serialize_course(course).get("status") or "active") == "deleting":
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
    if any(updates.get(field) is None for field in ("subject", "grade_level", "school_year_start") if field in updates):
        return _private_error(
            {"error": "bad_request", "detail": "course_metadata_incomplete"},
            status_code=400,
        )
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


def _course_lifecycle_error(exc: Exception):
    detail = str(exc).lower()
    if "metadata_incomplete" in detail:
        return _private_error({"error": "bad_request", "detail": "course_metadata_incomplete"}, status_code=400)
    if "confirmation_mismatch" in detail:
        return _private_error({"error": "bad_request", "detail": "deletion_confirmation_mismatch"}, status_code=400)
    if "not_active" in detail or "not_archived" in detail:
        return _private_error({"error": "conflict", "detail": "course_state_invalid"}, status_code=409)
    if "not_found" in detail or "no data found" in detail:
        return _private_error({"error": "not_found"}, status_code=404)
    return _private_error({"error": "forbidden"}, status_code=403)


async def _course_command(request: Request, course_id: str, method_name: str):
    user = getattr(request.state, "user", None)
    if not _role_in(user, "teacher"):
        return _private_error({"error": "forbidden"}, status_code=403)
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    try:
        result = getattr(_get_repo(), method_name)(course_id, _current_sub(user))
    except TeachingRepositoryUnavailable:
        raise
    except Exception as exc:
        return _course_lifecycle_error(exc)
    return _json_private(_serialize_course(result), status_code=200, vary_origin=True)


@teaching_courses_router.post("/api/teaching/courses/{course_id}/archive")
async def archive_course(request: Request, course_id: str):
    """Freeze an owned course and abandon unfinished dialog sessions atomically."""
    return await _course_command(request, course_id, "archive_course_owned")


@teaching_courses_router.post("/api/teaching/courses/{course_id}/restore")
async def restore_course(request: Request, course_id: str):
    """Restore a course that was archived accidentally."""
    return await _course_command(request, course_id, "restore_course_owned")


@teaching_courses_router.post("/api/teaching/courses/archive-batch")
async def archive_courses_batch(request: Request, payload: CourseArchiveBatchPayload):
    user = getattr(request.state, "user", None)
    if not _role_in(user, "teacher"):
        return _private_error({"error": "forbidden"}, status_code=403)
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    repo = _get_repo()
    try:
        course_ids = list(dict.fromkeys(payload.course_ids))
        for course_id in course_ids:
            if not _is_uuid_like(course_id):
                return _private_error({"error": "bad_request", "detail": "invalid_course_id"}, status_code=400)
        results = repo.archive_courses_owned(course_ids, _current_sub(user))
    except TeachingRepositoryUnavailable:
        raise
    except Exception as exc:
        return _course_lifecycle_error(exc)
    return _json_private([_serialize_course(item) for item in results], status_code=200, vary_origin=True)


@teaching_courses_router.get("/api/teaching/courses/{course_id}/deletion-impact")
async def get_course_deletion_impact(request: Request, course_id: str):
    user = getattr(request.state, "user", None)
    if not _role_in(user, "teacher"):
        return _private_error({"error": "forbidden"}, status_code=403)
    impact = _get_repo().get_course_deletion_impact(course_id=course_id, owner_sub=_current_sub(user))
    if not impact:
        return _private_error({"error": "not_found"}, status_code=404)
    return _json_private(impact, status_code=200)


@teaching_courses_router.post("/api/teaching/courses/{course_id}/deletion-jobs")
async def create_course_deletion_job(request: Request, course_id: str, payload: CourseDeletionPayload):
    user = getattr(request.state, "user", None)
    if not _role_in(user, "teacher"):
        return _private_error({"error": "forbidden"}, status_code=403)
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    try:
        job = _get_repo().queue_course_deletion(
            course_id=course_id,
            owner_sub=_current_sub(user),
            confirmation_title=payload.confirmation_title,
            confirm_student_data_loss=payload.confirm_student_data_loss,
        )
    except TeachingRepositoryUnavailable:
        raise
    except Exception as exc:
        return _course_lifecycle_error(exc)
    return _json_private(job, status_code=202, vary_origin=True)


@teaching_courses_router.get("/api/teaching/course-deletion-jobs")
async def list_course_deletion_jobs(
    request: Request,
    include_completed: bool = False,
    limit: int = 50,
    offset: int = 0,
):
    """List deletion jobs owned by the authenticated teacher."""

    user = getattr(request.state, "user", None)
    if not _role_in(user, "teacher"):
        return _private_error({"error": "forbidden"}, status_code=403)
    limit, offset = _clamp_limit_offset(limit=limit, offset=offset, default_limit=50, max_limit=100)
    try:
        jobs = _get_repo().list_course_deletion_jobs(
            owner_sub=_current_sub(user),
            include_completed=include_completed,
            limit=limit,
            offset=offset,
        )
    except TeachingRepositoryUnavailable:
        raise
    return _json_private(jobs, status_code=200)


@teaching_courses_router.get("/api/teaching/course-deletion-jobs/{job_id}")
async def get_course_deletion_job(request: Request, job_id: str):
    """Read one owner-scoped deletion job without leaking foreign IDs."""

    user = getattr(request.state, "user", None)
    if not _role_in(user, "teacher"):
        return _private_error({"error": "forbidden"}, status_code=403)
    if not _is_uuid_like(job_id):
        return _private_error({"error": "not_found"}, status_code=404)
    try:
        job = _get_repo().get_course_deletion_job(
            job_id=job_id,
            owner_sub=_current_sub(user),
        )
    except TeachingRepositoryUnavailable:
        raise
    if not job:
        return _private_error({"error": "not_found"}, status_code=404)
    return _json_private(job, status_code=200)
