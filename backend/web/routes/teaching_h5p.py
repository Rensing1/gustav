"""Task-centric H5P authoring routes for Teaching.

Why:
    Teachers edit H5P content through GUSTAV tasks, while the H5P sidecar owns
    editor/import/export primitives. Keeping this cohesive route group outside
    the large Teaching router reduces the hotspot without changing the public
    API surface.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse, Response
import httpx
from pydantic import BaseModel

from backend.web.routes import teaching_authoring
from backend.web.routes import teaching_task_services
from backend.web.routes import teaching_guards
from backend.web.routes.teaching_shared import (
    _current_sub,
    _is_uuid_like,
    _json_private,
    _private_error,
    _require_teacher,
)
from backend.web.routes.teaching_serialization import _serialize_task


teaching_h5p_router = APIRouter(tags=["Teaching"])
logger = logging.getLogger("gustav.web.teaching.h5p")
H5P_INTERNAL_BASE = (os.getenv("H5P_INTERNAL_BASE") or "http://h5p:3000").rstrip("/")
H5P_DEFAULT_MAX_UPLOAD_BYTES = 100 * 1024 * 1024
H5P_UPLOAD_CHUNK_BYTES = 1024 * 1024


class H5PTaskSavePayload(BaseModel):
    """Payload for saving H5P editor parameters through a task."""

    library: str
    params: dict[str, Any]


def _safe_header_value(value: object) -> str:
    """Return a conservative HTTP header value without control characters."""

    return str(value or "").replace("\r", "").replace("\n", "").strip()


def _h5p_max_upload_bytes() -> int:
    """Return the shared H5P package upload limit used before Web-to-H5P forwarding."""

    try:
        configured = int(str(os.getenv("H5P_MAX_UPLOAD_BYTES") or H5P_DEFAULT_MAX_UPLOAD_BYTES).strip())
    except (TypeError, ValueError):
        return H5P_DEFAULT_MAX_UPLOAD_BYTES
    return configured if configured > 0 else H5P_DEFAULT_MAX_UPLOAD_BYTES


async def _read_h5p_upload_file(file: UploadFile) -> tuple[bytes | None, JSONResponse | None]:
    """Read an H5P upload with a hard Web-side byte limit.

    The H5P sidecar also enforces this limit, but the Web process must count
    bytes first so a teacher or CLI token cannot force a full oversized package
    into Web memory before forwarding.
    """

    max_bytes = _h5p_max_upload_bytes()
    total = 0
    chunks: list[bytes] = []
    while True:
        read_size = min(H5P_UPLOAD_CHUNK_BYTES, max_bytes + 1 - total)
        if read_size <= 0:
            return None, _private_error(
                {"error": "payload_too_large", "detail": "h5p_upload_too_large"},
                status_code=413,
            )
        chunk = await file.read(read_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            return None, _private_error(
                {"error": "payload_too_large", "detail": "h5p_upload_too_large"},
                status_code=413,
            )
        chunks.append(chunk)
    return b"".join(chunks), None


def _h5p_internal_auth_headers(request: Request | None) -> dict[str, str]:
    """Build the trusted Web-to-H5P teacher context for CLI-authenticated calls."""

    if request is None or not getattr(request.state, "cli_token_id", None):
        return {}
    secret = (os.getenv("H5P_INTERNAL_SHARED_SECRET") or "").strip()
    if not secret:
        return {}
    user = getattr(request.state, "user", None)
    if not isinstance(user, dict):
        return {}
    sub = _safe_header_value(user.get("sub"))
    if not sub:
        return {}
    raw_roles = user.get("roles")
    if isinstance(raw_roles, list):
        roles = [_safe_header_value(role) for role in raw_roles if _safe_header_value(role)]
    else:
        roles = [_safe_header_value(user.get("role"))] if _safe_header_value(user.get("role")) else []
    if not roles:
        return {}
    return {
        "x-gustav-h5p-internal-secret": secret,
        "x-gustav-user-sub": sub,
        "x-gustav-user-name": _safe_header_value(user.get("name")) or sub,
        "x-gustav-user-roles": ",".join(roles),
    }


async def _request_h5p_service(
    method: str,
    path: str,
    *,
    request: Request | None = None,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    files: dict[str, tuple[str, bytes, str]] | None = None,
    timeout: float = 30.0,
) -> httpx.Response:
    """Send a request to the internal H5P service while forwarding session cookies.

    Why:
        The teacher-facing API should stay task-centric, but the existing H5P
        service still owns editor/player/import/export primitives. This helper
        keeps the wrapper endpoints thin and testable.
    """

    headers: dict[str, str] = {}
    if request is not None:
        cookie_header = str(request.headers.get("cookie") or "").strip()
        if cookie_header:
            headers["cookie"] = cookie_header
        origin = str(request.headers.get("origin") or "").strip()
        if origin:
            headers["origin"] = origin
        referer = str(request.headers.get("referer") or "").strip()
        if referer:
            headers["referer"] = referer
        headers.update(_h5p_internal_auth_headers(request))

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        return await client.request(
            method=method,
            url=f"{H5P_INTERNAL_BASE}{path}",
            params=params,
            json=json_body,
            files=files,
            headers=headers,
        )


async def _call_request_h5p_service(
    method: str,
    path: str,
    *,
    request: Request | None = None,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    files: dict[str, tuple[str, bytes, str]] | None = None,
) -> httpx.Response:
    """Call the active H5P helper so tests can replace service I/O explicitly."""

    return await _request_h5p_service(
        method,
        path,
        request=request,
        params=params,
        json_body=json_body,
        files=files,
    )


def _get_owned_h5p_task(unit_id: str, section_id: str, task_id: str, author_sub: str) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    """Resolve an author-owned H5P task or return a fail-closed API error."""

    try:
        tasks = teaching_task_services._get_tasks_service().list_tasks(unit_id, section_id, author_sub)
    except PermissionError:
        return None, _private_error({"error": "forbidden"}, status_code=403)
    except LookupError:
        return None, _private_error({"error": "not_found"}, status_code=404)

    task = next((item for item in tasks if str(_serialize_task(item).get("id") or "") == task_id), None)
    if task is None:
        return None, _private_error({"error": "not_found"}, status_code=404)
    serialized = _serialize_task(task)
    if str(serialized.get("kind") or "") != "h5p":
        return None, _private_error({"error": "not_found"}, status_code=404)
    return serialized, None


def _proxy_h5p_error_response(upstream: httpx.Response) -> JSONResponse:
    """Map upstream H5P failures to private JSON responses."""

    payload: dict[str, Any]
    try:
        candidate = upstream.json()
        payload = candidate if isinstance(candidate, dict) else {"error": "bad_gateway"}
    except Exception:
        payload = {"error": "bad_gateway"}
    status_code = int(upstream.status_code or 502)
    if status_code < 400 or status_code >= 600:
        status_code = 502
    return _private_error(payload, status_code=status_code)


async def _rollback_h5p_content(content_id: str, request: Request | None) -> None:
    """Delete a just-created H5P content item after a local persist failure.

    Why:
        The task-centric teaching API must not leave orphaned H5P content behind
        when the upstream create/import succeeded but the local task update
        failed afterwards.
    """

    content_id = str(content_id or "").strip()
    if not content_id:
        return
    try:
        response = await _call_request_h5p_service("DELETE", f"/contents/{content_id}", request=request)
        if int(response.status_code or 500) not in (204, 404):
            logger.warning(
                "H5P rollback delete failed content_id=%s status=%s",
                content_id,
                int(response.status_code or 500),
            )
    except Exception as exc:
        logger.warning(
            "H5P rollback delete failed content_id=%s reason=%s",
            content_id,
            exc.__class__.__name__,
        )


@teaching_h5p_router.get("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/editor-model")
async def get_task_h5p_editor_model(request: Request, unit_id: str, section_id: str, task_id: str):
    """Return the H5P editor model for an owned H5P task."""

    user, error = _require_teacher(request)
    if error:
        return error
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return _private_error({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    if not _is_uuid_like(task_id):
        return _private_error({"error": "bad_request", "detail": "invalid_task_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub)
    if guard:
        return guard
    task, task_error = _get_owned_h5p_task(unit_id, section_id, task_id, sub)
    if task_error:
        return task_error

    params: dict[str, object] | None = None
    content_id = str(((task or {}).get("h5p") or {}).get("content_id") or "").strip()
    if content_id:
        params = {"content_id": content_id}

    try:
        upstream = await _call_request_h5p_service("GET", "/editor/model", request=request, params=params)
    except httpx.RequestError:
        return _private_error({"error": "service_unavailable"}, status_code=503)
    if not upstream.is_success:
        return _proxy_h5p_error_response(upstream)
    try:
        return _json_private(upstream.json(), status_code=200)
    except Exception:
        return _private_error({"error": "bad_gateway"}, status_code=502)


@teaching_h5p_router.post("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/save")
async def save_task_h5p_content(
    request: Request,
    unit_id: str,
    section_id: str,
    task_id: str,
    payload: H5PTaskSavePayload,
):
    """Create or update task-linked H5P content and persist the content id on the task."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return _private_error({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    if not _is_uuid_like(task_id):
        return _private_error({"error": "bad_request", "detail": "invalid_task_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub)
    if guard:
        return guard
    task, task_error = _get_owned_h5p_task(unit_id, section_id, task_id, sub)
    if task_error:
        return task_error

    current_content_id = str(((task or {}).get("h5p") or {}).get("content_id") or "").strip()
    path = f"/contents/{current_content_id}" if current_content_id else "/contents"
    method = "PATCH" if current_content_id else "POST"

    try:
        upstream = await _call_request_h5p_service(
            method,
            path,
            request=request,
            json_body={"library": payload.library, "params": payload.params},
        )
    except httpx.RequestError:
        return _private_error({"error": "service_unavailable"}, status_code=503)
    if not upstream.is_success:
        return _proxy_h5p_error_response(upstream)
    try:
        upstream_payload = upstream.json()
    except Exception:
        return _private_error({"error": "bad_gateway"}, status_code=502)

    new_content_id = str((upstream_payload or {}).get("content_id") or "").strip()
    if not new_content_id:
        return _private_error({"error": "bad_gateway"}, status_code=502)
    try:
        teaching_task_services._get_tasks_service().update_task(
            unit_id,
            section_id,
            task_id,
            sub,
            h5p={"content_id": new_content_id, "display_options": ((task or {}).get("h5p") or {}).get("display_options") or {}},
        )
    except ValueError as exc:
        await _rollback_h5p_content(new_content_id, request)
        detail = str(exc) or "invalid_input"
        if detail not in {"invalid_h5p_config", "invalid_task_kind_config"}:
            detail = "invalid_input"
        return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
    except LookupError:
        await _rollback_h5p_content(new_content_id, request)
        return _private_error({"error": "not_found"}, status_code=404)
    except PermissionError:
        await _rollback_h5p_content(new_content_id, request)
        return _private_error({"error": "forbidden"}, status_code=403)
    except Exception:
        await _rollback_h5p_content(new_content_id, request)
        return _private_error({"error": "internal_error"}, status_code=500)
    return _json_private({"content_id": new_content_id, "metadata": (upstream_payload or {}).get("metadata") or {}}, status_code=200)


@teaching_h5p_router.post("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/import")
async def import_task_h5p_content(
    request: Request,
    unit_id: str,
    section_id: str,
    task_id: str,
    file: UploadFile = File(...),
):
    """Import an H5P archive and link the resulting content to the task."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return _private_error({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    if not _is_uuid_like(task_id):
        return _private_error({"error": "bad_request", "detail": "invalid_task_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub)
    if guard:
        return guard
    task, task_error = _get_owned_h5p_task(unit_id, section_id, task_id, sub)
    if task_error:
        return task_error
    file_bytes, upload_error = await _read_h5p_upload_file(file)
    if upload_error:
        return upload_error
    if not file_bytes:
        return _private_error({"error": "bad_request", "detail": "invalid_h5p_file"}, status_code=400)

    try:
        upstream = await _call_request_h5p_service(
            "POST",
            "/contents/import",
            request=request,
            files={"file": (file.filename or "content.h5p", file_bytes, file.content_type or "application/zip")},
        )
    except httpx.RequestError:
        return _private_error({"error": "service_unavailable"}, status_code=503)
    if not upstream.is_success:
        return _proxy_h5p_error_response(upstream)
    try:
        upstream_payload = upstream.json()
    except Exception:
        return _private_error({"error": "bad_gateway"}, status_code=502)

    new_content_id = str((upstream_payload or {}).get("content_id") or "").strip()
    if not new_content_id:
        return _private_error({"error": "bad_gateway"}, status_code=502)
    try:
        updated = teaching_task_services._get_tasks_service().update_task(
            unit_id,
            section_id,
            task_id,
            sub,
            h5p={"content_id": new_content_id, "display_options": ((task or {}).get("h5p") or {}).get("display_options") or {}},
        )
    except ValueError as exc:
        await _rollback_h5p_content(new_content_id, request)
        detail = str(exc) or "invalid_input"
        if detail not in {"invalid_h5p_config", "invalid_task_kind_config"}:
            detail = "invalid_input"
        return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
    except LookupError:
        await _rollback_h5p_content(new_content_id, request)
        return _private_error({"error": "not_found"}, status_code=404)
    except PermissionError:
        await _rollback_h5p_content(new_content_id, request)
        return _private_error({"error": "forbidden"}, status_code=403)
    except Exception:
        await _rollback_h5p_content(new_content_id, request)
        return _private_error({"error": "internal_error"}, status_code=500)
    return _json_private(_serialize_task(updated), status_code=200)


@teaching_h5p_router.get("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/export")
async def export_task_h5p_content(request: Request, unit_id: str, section_id: str, task_id: str):
    """Export the currently linked H5P content for an owned task."""

    user, error = _require_teacher(request)
    if error:
        return error
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return _private_error({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    if not _is_uuid_like(task_id):
        return _private_error({"error": "bad_request", "detail": "invalid_task_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub)
    if guard:
        return guard
    task, task_error = _get_owned_h5p_task(unit_id, section_id, task_id, sub)
    if task_error:
        return task_error
    content_id = str(((task or {}).get("h5p") or {}).get("content_id") or "").strip()
    if not content_id:
        return _private_error({"error": "not_found"}, status_code=404)

    try:
        upstream = await _call_request_h5p_service("GET", f"/contents/{content_id}/export", request=request)
    except httpx.RequestError:
        return _private_error({"error": "service_unavailable"}, status_code=503)
    if not upstream.is_success:
        return _proxy_h5p_error_response(upstream)
    headers = {"Cache-Control": "private, no-store"}
    content_disposition = upstream.headers.get("content-disposition")
    if content_disposition:
        headers["Content-Disposition"] = content_disposition
    return Response(
        content=upstream.content,
        media_type=upstream.headers.get("content-type") or "application/zip",
        headers=headers,
    )


@teaching_h5p_router.post("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/reset")
async def reset_task_h5p_content(request: Request, unit_id: str, section_id: str, task_id: str):
    """Unlink the H5P content from a task without deleting upstream content."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return _private_error({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    if not _is_uuid_like(task_id):
        return _private_error({"error": "bad_request", "detail": "invalid_task_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub)
    if guard:
        return guard
    task, task_error = _get_owned_h5p_task(unit_id, section_id, task_id, sub)
    if task_error:
        return task_error
    updated = teaching_task_services._get_tasks_service().update_task(
        unit_id,
        section_id,
        task_id,
        sub,
        h5p={"content_id": None, "display_options": ((task or {}).get("h5p") or {}).get("display_options") or {}},
    )
    return _json_private(_serialize_task(updated), status_code=200)


@teaching_h5p_router.post("/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}/h5p/import")
async def import_module_task_h5p_content(
    request: Request,
    unit_id: str,
    module_id: str,
    task_id: str,
    file: UploadFile = File(...),
):
    """Import H5P content for a module-backed task with write scope only."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        task_id=task_id,
    )
    if error:
        return error
    return await import_task_h5p_content(request, unit_id, str(section_id), task_id, file)


@teaching_h5p_router.post("/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}/h5p/reset")
async def reset_module_task_h5p_content(request: Request, unit_id: str, module_id: str, task_id: str):
    """Unlink H5P content for a module-backed task with write scope only."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        task_id=task_id,
    )
    if error:
        return error
    return await reset_task_h5p_content(request, unit_id, str(section_id), task_id)
