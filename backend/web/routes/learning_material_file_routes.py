"""Learner material-file download routes.

Why:
    Material file downloads have their own visibility lookup, storage adapter
    boundary, and legacy alias semantics. Keeping those route handlers here
    reduces the Learning adapter hotspot without changing the public API.
"""

from __future__ import annotations

import importlib
import os
import sys as _sys
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from backend.storage.config import get_materials_max_upload_bytes
from backend.web.material_file_access import (
    MaterialVisibilityLookupUnavailable,
    load_student_material_file_metadata,
)


learning_material_file_router = APIRouter(tags=["Learning"])


def _learning_module():
    module = _sys.modules.get("backend.web.routes.learning")
    if module is None:  # pragma: no cover - defensive import fallback
        module = importlib.import_module("backend.web.routes.learning")
    return module


def _require_student(request: Request):
    return _learning_module()._require_student(request)


def _cache_headers_error() -> dict[str, str]:
    return _learning_module()._cache_headers_error()


def _normalize_download_disposition(raw: str | None, *, default: str = "inline") -> str | None:
    return _learning_module()._normalize_download_disposition(raw, default=default)


def _get_repo():
    return _learning_module()._get_repo()


def _safe_download_filename(filename: str | None, fallback: str) -> str:
    return _learning_module()._safe_download_filename(filename, fallback)


def _teaching_storage_adapter() -> object | None:
    return _learning_module()._teaching_storage_adapter()


async def _download_storage_object_via_presign(**kwargs):  # noqa: ANN003
    return await _learning_module()._download_storage_object_via_presign(**kwargs)


@learning_material_file_router.get("/api/learning/courses/{course_id}/materials/{material_id}/file")
async def get_material_file(
    request: Request,
    course_id: str,
    material_id: str,
    disposition: str | None = None,
):
    """Stream a visible material file through the canonical same-origin route."""

    user, error = _require_student(request)
    if error:
        return error

    normalized_disposition = _normalize_download_disposition(disposition)
    if normalized_disposition is None:
        return JSONResponse({"error": "bad_request", "detail": "invalid_disposition"}, status_code=400, headers=_cache_headers_error())

    try:
        UUID(course_id)
        UUID(material_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers_error())

    repo = _get_repo()
    try:
        metadata = load_student_material_file_metadata(
            repo=repo,
            student_sub=str(user.get("sub", "")),
            course_id=str(course_id),
            material_id=str(material_id),
        )
    except MaterialVisibilityLookupUnavailable:
        return JSONResponse(
            {"error": "service_unavailable", "detail": "authorization_unavailable"},
            status_code=503,
            headers=_cache_headers_error(),
        )

    if metadata is None:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    mime_type = str(metadata.mime_type or "").strip().lower()
    storage_key = str(metadata.storage_key or "").strip()
    filename = _safe_download_filename(metadata.filename_original or os.path.basename(storage_key), "material.bin")
    size_bytes = int(metadata.size_bytes or 0)
    if not storage_key or not mime_type:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    body = await _download_storage_object_via_presign(
        bucket=(__import__("backend.teaching.services.materials", fromlist=["MaterialFileSettings"]).MaterialFileSettings().storage_bucket),
        key=storage_key,
        disposition=normalized_disposition,
        max_bytes=max(get_materials_max_upload_bytes(), size_bytes),
        adapter=_teaching_storage_adapter(),
    )
    if body is None:
        return JSONResponse({"error": "service_unavailable"}, status_code=503, headers=_cache_headers_error())

    return Response(
        content=body,
        media_type=mime_type or "application/octet-stream",
        headers={
            "Cache-Control": "private, no-store",
            "Vary": "Origin",
            "Content-Disposition": f'{normalized_disposition}; filename="{filename}"',
        },
    )


@learning_material_file_router.get("/api/learning/courses/{course_id}/sections/{section_id}/materials/{material_id}/file")
async def get_material_file_legacy_alias(
    request: Request,
    course_id: str,
    section_id: str,
    material_id: str,
    disposition: str | None = None,
):
    """Stream a visible material file through the legacy section-based alias."""

    try:
        UUID(course_id)
        UUID(section_id)
        UUID(material_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers_error())

    user, error = _require_student(request)
    if error:
        return error

    repo = _get_repo()
    try:
        metadata = load_student_material_file_metadata(
            repo=repo,
            student_sub=str(user.get("sub", "")),
            course_id=str(course_id),
            material_id=str(material_id),
        )
    except MaterialVisibilityLookupUnavailable:
        return JSONResponse(
            {"error": "service_unavailable", "detail": "authorization_unavailable"},
            status_code=503,
            headers=_cache_headers_error(),
        )

    if metadata is None or str(metadata.section_id) != str(section_id):
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    return await get_material_file(
        request=request,
        course_id=course_id,
        material_id=material_id,
        disposition=disposition,
    )
