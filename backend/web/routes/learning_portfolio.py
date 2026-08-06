"""Private portfolio and export routes for learners.

The route layer deliberately returns only rows produced by the personal
portfolio database functions. It never falls back to teacher-facing course or
submission queries, so archived memberships cannot widen data access.
"""

from __future__ import annotations

import importlib
import os
import sys
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response


learning_portfolio_router = APIRouter(tags=["Learning"])


def _learning_module():
    module = sys.modules.get("backend.web.routes.learning")
    if module is None:  # pragma: no cover - defensive import fallback
        module = importlib.import_module("backend.web.routes.learning")
    return module


def _error(payload: dict, status_code: int) -> JSONResponse:
    return JSONResponse(payload, status_code=status_code, headers=_learning_module()._cache_headers_error())


def _job_payload(job: dict) -> dict:
    status = str(job.get("status") or "pending")
    return {
        "id": str(job.get("id") or ""),
        "course_id": str(job.get("course_id") or ""),
        "status": status,
        "requested_at": job.get("requested_at"),
        "expires_at": job.get("expires_at"),
        "download_href": f"/api/learning/exports/{job.get('id')}/download" if status == "ready" else None,
        "error_code": job.get("error_code"),
    }


def _personal_course(repo, *, course_id: str, student_sub: str) -> dict | None:
    for scope in ("current", "past"):
        courses = repo.list_personal_courses(student_sub=student_sub, scope=scope, limit=100, offset=0)
        match = next((item for item in courses if str(item.get("id") or "") == course_id), None)
        if match:
            return dict(match)
    return None


@learning_portfolio_router.get("/api/learning/courses/{course_id}/portfolio")
async def get_personal_course_portfolio(request: Request, course_id: str):
    """Return only the caller's final learning evidence for one course."""

    user, auth_error = _learning_module()._require_student(request)
    if auth_error:
        return auth_error
    try:
        UUID(course_id)
    except ValueError:
        return _error({"error": "bad_request", "detail": "invalid_uuid"}, 400)

    student_sub = str(user.get("sub") or "")
    repo = _learning_module()._get_repo()
    course = _personal_course(repo, course_id=course_id, student_sub=student_sub)
    if course is None:
        return _error({"error": "not_found"}, 404)

    submissions = []
    for raw in repo.personal_course_portfolio(course_id=course_id, student_sub=student_sub):
        item = dict(raw)
        storage_key = str(item.pop("storage_key", "") or "")
        item["file_name"] = os.path.basename(storage_key) if storage_key else None
        item["file_href"] = (
            f"/api/learning/portfolio/submissions/{quote(str(item.get('id') or ''), safe='')}/file"
            if storage_key else None
        )
        item.pop("mime_type", None)
        submissions.append(item)

    latest_method = getattr(repo, "get_latest_learning_export_job", None)
    latest = latest_method(course_id=course_id, student_sub=student_sub) if callable(latest_method) else None
    return JSONResponse(
        {
            "course": course,
            "submissions": submissions,
            "export_href": f"/api/learning/courses/{course_id}/exports",
            "latest_export": _job_payload(latest) if latest else None,
        },
        headers=_learning_module()._cache_headers_success(),
    )


@learning_portfolio_router.post("/api/learning/courses/{course_id}/exports")
async def create_personal_course_export(request: Request, course_id: str):
    """Queue one private, expiring export snapshot for the current learner."""

    user, auth_error = _learning_module()._require_student(request)
    if auth_error:
        return auth_error
    if not _learning_module()._require_strict_same_origin(request):
        return _error({"error": "forbidden", "detail": "csrf_failed"}, 403)
    try:
        UUID(course_id)
    except ValueError:
        return _error({"error": "bad_request", "detail": "invalid_uuid"}, 400)

    student_sub = str(user.get("sub") or "")
    repo = _learning_module()._get_repo()
    if _personal_course(repo, course_id=course_id, student_sub=student_sub) is None:
        return _error({"error": "not_found"}, 404)
    try:
        job = repo.create_learning_export_job(course_id=course_id, student_sub=student_sub)
    except LookupError:
        return _error({"error": "not_found"}, 404)
    return JSONResponse(_job_payload(job), status_code=202, headers=_learning_module()._cache_headers_success())


@learning_portfolio_router.get("/api/learning/exports/{export_id}")
async def get_personal_export(request: Request, export_id: str):
    """Return export status without exposing its private storage key."""

    user, auth_error = _learning_module()._require_student(request)
    if auth_error:
        return auth_error
    try:
        UUID(export_id)
    except ValueError:
        return _error({"error": "bad_request", "detail": "invalid_uuid"}, 400)
    job = _learning_module()._get_repo().get_learning_export_job(
        export_id=export_id, student_sub=str(user.get("sub") or "")
    )
    if not job:
        return _error({"error": "not_found"}, 404)
    return JSONResponse(_job_payload(job), headers=_learning_module()._cache_headers_success())


@learning_portfolio_router.get("/api/learning/exports/{export_id}/download")
async def download_personal_export(request: Request, export_id: str):
    """Proxy a ready ZIP through the authenticated application boundary."""

    user, auth_error = _learning_module()._require_student(request)
    if auth_error:
        return auth_error
    try:
        UUID(export_id)
    except ValueError:
        return _error({"error": "bad_request", "detail": "invalid_uuid"}, 400)
    job = _learning_module()._get_repo().get_learning_export_job(
        export_id=export_id, student_sub=str(user.get("sub") or "")
    )
    if not job:
        return _error({"error": "not_found"}, 404)
    status = str(job.get("status") or "")
    if status == "expired":
        return _error({"error": "conflict", "detail": "export_expired"}, 409)
    if status != "ready" or not job.get("storage_key"):
        return _error({"error": "conflict", "detail": "export_not_ready"}, 409)
    body = await _learning_module()._download_storage_object_via_presign(
        bucket="learning-exports",
        key=str(job["storage_key"]),
        disposition="attachment",
        max_bytes=int(os.getenv("LEARNING_EXPORT_MAX_BYTES", str(1024 * 1024 * 1024))),
    )
    if body is None:
        return _error({"error": "service_unavailable"}, 503)
    return Response(
        content=body,
        media_type="application/zip",
        headers={
            "Cache-Control": "private, no-store",
            "Vary": "Origin",
            "Content-Disposition": f'attachment; filename="gustav-lernarchiv-{export_id}.zip"',
        },
    )


@learning_portfolio_router.get("/api/learning/portfolio/submissions/{submission_id}/file")
async def download_personal_portfolio_file(request: Request, submission_id: str):
    """Return one original file only after matching it in the caller's portfolio."""

    user, auth_error = _learning_module()._require_student(request)
    if auth_error:
        return auth_error
    try:
        UUID(submission_id)
    except ValueError:
        return _error({"error": "bad_request", "detail": "invalid_uuid"}, 400)
    repo = _learning_module()._get_repo()
    student_sub = str(user.get("sub") or "")
    submission = None
    for scope in ("current", "past"):
        for course in repo.list_personal_courses(student_sub=student_sub, scope=scope, limit=100, offset=0):
            for item in repo.personal_course_portfolio(course_id=str(course.get("id") or ""), student_sub=student_sub):
                if str(item.get("id") or "") == submission_id:
                    submission = item
                    break
            if submission:
                break
        if submission:
            break
    if not submission or not submission.get("storage_key"):
        return _error({"error": "not_found"}, 404)
    body = await _learning_module()._download_storage_object_via_presign(
        bucket=_learning_module()._storage_bucket(),
        key=str(submission["storage_key"]),
        disposition="attachment",
        max_bytes=_learning_module()._max_upload_bytes(),
    )
    if body is None:
        return _error({"error": "service_unavailable"}, 503)
    filename = _learning_module()._safe_download_filename(
        os.path.basename(str(submission["storage_key"])), "submission.bin"
    )
    return Response(
        content=body,
        media_type=str(submission.get("mime_type") or "application/octet-stream"),
        headers={
            "Cache-Control": "private, no-store",
            "Vary": "Origin",
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
