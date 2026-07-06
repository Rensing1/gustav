"""Learning submission history and file-download routes."""

from __future__ import annotations

import importlib
import os
import sys as _sys
from typing import Any
from urllib.parse import quote as _quote
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response


learning_submission_files_router = APIRouter(tags=["Learning"])


def _learning_module():
    module = _sys.modules.get("backend.web.routes.learning")
    if module is None:  # pragma: no cover - defensive import fallback
        module = importlib.import_module("backend.web.routes.learning")
    return module


def _cache_headers_success() -> dict[str, str]:
    return _learning_module()._cache_headers_success()


def _cache_headers_error() -> dict[str, str]:
    return _learning_module()._cache_headers_error()


def _require_student(request: Request):
    return _learning_module()._require_student(request)


def _get_repo():
    return _learning_module()._get_repo()


def _list_submissions_use_case():
    return _learning_module().ListSubmissionsUseCase


def _list_submissions_input():
    return _learning_module().ListSubmissionsInput


def _storage_bucket() -> str:
    return str(_learning_module()._storage_bucket())


def _max_upload_bytes() -> int:
    return int(_learning_module()._max_upload_bytes())


def _safe_download_filename(filename: str | None, fallback: str) -> str:
    return _learning_module()._safe_download_filename(filename, fallback)


async def _download_storage_object_via_presign(**kwargs):  # noqa: ANN003
    return await _learning_module()._download_storage_object_via_presign(**kwargs)


def submission_file_href(*, course_id: str, task_id: str, submission_id: str, disposition: str) -> str:
    """Return a stable same-origin file URL for a learner submission."""

    return (
        f"/api/learning/courses/{_quote(str(course_id), safe='')}/tasks/{_quote(str(task_id), safe='')}"
        f"/submissions/{_quote(str(submission_id), safe='')}/file?disposition={_quote(str(disposition), safe='')}"
    )


def _is_uuid_like(value: object) -> bool:
    try:
        UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return False
    return True


def attach_submission_files(submission: dict[str, Any], *, course_id: str, task_id: str) -> dict[str, Any]:
    """Attach short-lived artifact URLs for learner-visible submission history."""

    payload = dict(submission or {})
    payload["files"] = []

    kind = str(payload.get("kind") or "").strip().lower()
    storage_key = str(payload.get("storage_key") or "").strip()
    mime_type = str(payload.get("mime_type") or "").strip().lower()
    size_bytes = payload.get("size_bytes")
    if kind not in {"image", "file"} or not storage_key or not mime_type:
        return payload

    try:
        size_int = int(size_bytes)
    except (TypeError, ValueError):
        return payload
    if size_int <= 0:
        return payload

    submission_id = str(payload.get("id") or "").strip()
    if not (_is_uuid_like(submission_id) and _is_uuid_like(course_id) and _is_uuid_like(task_id)):
        return payload

    url = submission_file_href(course_id=course_id, task_id=task_id, submission_id=submission_id, disposition="inline")
    download_url = submission_file_href(
        course_id=course_id,
        task_id=task_id,
        submission_id=submission_id,
        disposition="attachment",
    )

    payload["files"] = [
        {
            "mime": mime_type,
            "size": size_int,
            "url": url,
            "download_url": download_url,
        }
    ]
    return payload


def normalize_download_disposition(raw: str | None, *, default: str = "inline") -> str | None:
    disposition = (raw or default).strip().lower()
    if disposition not in {"inline", "attachment"}:
        return None
    return disposition


@learning_submission_files_router.get("/api/learning/courses/{course_id}/tasks/{task_id}/submissions")
async def list_submissions(
    request: Request,
    course_id: str,
    task_id: str,
    limit: int = 20,
    offset: int = 0,
):
    """Return the caller's submission history for a task."""

    user, error = _require_student(request)
    if error:
        return error

    try:
        UUID(course_id)
        UUID(task_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers_error())

    input_data = _list_submissions_input()(
        course_id=course_id,
        task_id=task_id,
        student_sub=str(user.get("sub", "")),
        limit=limit,
        offset=offset,
    )

    try:
        submissions = _list_submissions_use_case()(_get_repo()).execute(input_data)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_cache_headers_error())
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    decorated = [
        attach_submission_files(submission, course_id=course_id, task_id=task_id)
        for submission in submissions
    ]
    return JSONResponse(decorated, status_code=200, headers=_cache_headers_success())


@learning_submission_files_router.get("/api/learning/courses/{course_id}/tasks/{task_id}/submissions/{submission_id}/file")
async def get_submission_file(
    request: Request,
    course_id: str,
    task_id: str,
    submission_id: str,
    disposition: str | None = None,
):
    """Stream a learner-visible submission file through a stable same-origin route."""

    user, error = _require_student(request)
    if error:
        return error

    normalized_disposition = normalize_download_disposition(disposition)
    if normalized_disposition is None:
        return JSONResponse({"error": "bad_request", "detail": "invalid_disposition"}, status_code=400, headers=_cache_headers_error())

    try:
        UUID(course_id)
        UUID(task_id)
        UUID(submission_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers_error())

    try:
        submissions = _list_submissions_use_case()(_get_repo()).execute(
            _list_submissions_input()(
                course_id=course_id,
                task_id=task_id,
                student_sub=str(user.get("sub", "")),
                limit=100,
                offset=0,
            )
        )
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_cache_headers_error())
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    submission = next((item for item in submissions if str(item.get("id") or "") == submission_id), None)
    if not isinstance(submission, dict):
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    storage_key = str(submission.get("storage_key") or "").strip()
    mime_type = str(submission.get("mime_type") or "").strip().lower()
    kind = str(submission.get("kind") or "").strip().lower()
    try:
        size_bytes = max(0, int(submission.get("size_bytes") or 0))
    except (TypeError, ValueError):
        size_bytes = 0
    if kind not in {"image", "file"} or not storage_key or not mime_type:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    body = await _download_storage_object_via_presign(
        bucket=_storage_bucket(),
        key=storage_key,
        disposition=normalized_disposition,
        max_bytes=max(_max_upload_bytes(), size_bytes),
    )
    if body is None:
        return JSONResponse({"error": "service_unavailable"}, status_code=503, headers=_cache_headers_error())

    filename = _safe_download_filename(os.path.basename(storage_key), "submission.bin")
    return Response(
        content=body,
        media_type=mime_type or "application/octet-stream",
        headers={
            "Cache-Control": "private, no-store",
            "Vary": "Origin",
            "Content-Disposition": f'{normalized_disposition}; filename="{filename}"',
        },
    )
