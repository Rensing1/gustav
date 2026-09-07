"""Learner material-file download routes.

Why:
    Material file downloads have their own visibility lookup, storage adapter
    boundary, and legacy alias semantics. Explicit providers isolate these reads
    from global Learning/Teaching adapters. Keeping those route handlers here
    reduces the Learning adapter hotspot without changing the public API.
"""

from __future__ import annotations

import os
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from backend.storage.config import (
    get_materials_bucket,
    get_materials_max_upload_bytes,
    get_simulation_max_upload_bytes,
)
from backend.web.learning_material_providers import learning_material_providers
from backend.web.material_file_access import (
    MaterialVisibilityLookupUnavailable,
)
from backend.web.routes.app_session_helpers import current_user, private_headers
from backend.web.routes.learning_submission_files import (
    normalize_download_disposition as _normalize_download_disposition,
)
from backend.web.routes.teaching_submission_files import (
    safe_download_filename as _safe_download_filename,
)
from backend.web.security.guards import has_role
from backend.web.simulation_player import build_simulation_response

learning_material_file_router = APIRouter(tags=["Learning"])


def _cache_headers_error() -> dict[str, str]:
    return {**private_headers(), "Vary": "Origin"}


def _require_student(request: Request):
    """Reject unauthenticated/non-student callers before resolving dependencies."""
    user = current_user(request)
    if not user:
        return None, JSONResponse(
            {"error": "unauthenticated"}, status_code=401, headers=_cache_headers_error()
        )
    if not has_role(user, "student"):
        return None, JSONResponse(
            {"error": "forbidden"}, status_code=403, headers=_cache_headers_error()
        )
    return user, None


@learning_material_file_router.get(
    "/api/learning/courses/{course_id}/materials/{material_id}/simulation"
)
async def get_material_simulation(request: Request, course_id: str, material_id: str):
    """Stream a visible simulation without revealing a storage URL."""
    user, error = _require_student(request)
    if error:
        return error
    try:
        UUID(course_id)
        UUID(material_id)
    except ValueError:
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_uuid"},
            status_code=400,
            headers=_cache_headers_error(),
        )
    providers = learning_material_providers(request)
    try:
        metadata = await run_in_threadpool(
            providers.asset_metadata,
            student_sub=str(user.get("sub", "")),
            course_id=course_id,
            material_id=material_id,
        )
    except MaterialVisibilityLookupUnavailable:
        return JSONResponse(
            {"error": "service_unavailable", "detail": "authorization_unavailable"},
            status_code=503,
            headers=_cache_headers_error(),
        )
    if metadata is None or metadata.kind != "simulation" or metadata.mime_type != "text/html":
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    payload = await providers.download_object(
        bucket=get_materials_bucket(),
        key=metadata.storage_key,
        disposition="inline",
        max_bytes=get_simulation_max_upload_bytes(),
    )
    if payload is None:
        return JSONResponse(
            {"error": "service_unavailable"}, status_code=503, headers=_cache_headers_error()
        )
    return build_simulation_response(payload)


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
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_disposition"},
            status_code=400,
            headers=_cache_headers_error(),
        )

    try:
        UUID(course_id)
        UUID(material_id)
    except ValueError:
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_uuid"},
            status_code=400,
            headers=_cache_headers_error(),
        )

    providers = learning_material_providers(request)
    try:
        metadata = await run_in_threadpool(
            providers.file_metadata,
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
    filename = _safe_download_filename(
        metadata.filename_original or os.path.basename(storage_key), "material.bin"
    )
    size_bytes = int(metadata.size_bytes or 0)
    if not storage_key or not mime_type:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    body = await providers.download_object(
        bucket=get_materials_bucket(),
        key=storage_key,
        disposition=normalized_disposition,
        max_bytes=max(get_materials_max_upload_bytes(), size_bytes),
    )
    if body is None:
        return JSONResponse(
            {"error": "service_unavailable"}, status_code=503, headers=_cache_headers_error()
        )

    return Response(
        content=body,
        media_type=mime_type or "application/octet-stream",
        headers={
            "Cache-Control": "private, no-store",
            "Vary": "Origin",
            "Content-Disposition": f'{normalized_disposition}; filename="{filename}"',
        },
    )


@learning_material_file_router.get(
    "/api/learning/courses/{course_id}/sections/{section_id}/materials/{material_id}/file"
)
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
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_uuid"},
            status_code=400,
            headers=_cache_headers_error(),
        )

    user, error = _require_student(request)
    if error:
        return error

    providers = learning_material_providers(request)
    try:
        metadata = await run_in_threadpool(
            providers.file_metadata,
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
