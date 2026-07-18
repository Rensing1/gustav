"""Teaching unit routes.

Why:
    Unit endpoints are a core authoring surface. The split router owns their
    HTTP behavior directly so the large `teaching.py` adapter can keep shrinking.
"""

from __future__ import annotations

import logging
import sys as _sys

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from backend.teaching.errors import TeachingRepositoryUnavailable
from backend.web.routes import teaching_guards
from backend.web.routes.teaching import (
    _MODULAR_UNIT_CREATE_REQUIRED_METHODS,
    _collect_unit_delete_storage_objects as _default_collect_unit_delete_storage_objects,
    _delete_unit_storage_objects as _default_delete_unit_storage_objects,
    _get_repo,
    _require_modular_repo_methods,
)
from backend.web.routes.teaching_payloads import UnitCreatePayload, UnitUpdatePayload
from backend.web.routes.teaching_serialization import _serialize_unit
from backend.web.routes.teaching_shared import (
    _current_sub,
    _is_uuid_like,
    _json_private,
    _private_error,
    _require_teacher,
)
from backend.web.routes.teaching_validation import clamp_limit_offset as _clamp_limit_offset


teaching_units_router = APIRouter(tags=["Teaching"])
logger = logging.getLogger("gustav.web.teaching.units")


def _current_collect_unit_delete_storage_objects():
    module = _sys.modules.get("backend.web.routes.teaching")
    return getattr(module, "_collect_unit_delete_storage_objects", _default_collect_unit_delete_storage_objects)


def _current_delete_unit_storage_objects():
    module = _sys.modules.get("backend.web.routes.teaching")
    return getattr(module, "_delete_unit_storage_objects", _default_delete_unit_storage_objects)


@teaching_units_router.get("/api/teaching/units")
async def list_units(request: Request, limit: int = 20, offset: int = 0):
    """Return units authored by the current teacher."""

    user, error = _require_teacher(request)
    if error:
        return error
    limit, offset = _clamp_limit_offset(limit=limit, offset=offset, default_limit=20, max_limit=50)
    sub = _current_sub(user)
    try:
        units = _get_repo().list_units_for_author(author_id=sub, limit=limit, offset=offset)
    except TeachingRepositoryUnavailable:
        raise
    except Exception as exc:
        logger.warning("list_units failed reason=unexpected_error err=%s", exc.__class__.__name__)
        return _private_error({"error": "forbidden"}, status_code=403)
    return _json_private([_serialize_unit(unit) for unit in units], status_code=200)


@teaching_units_router.post("/api/teaching/units")
async def create_unit(request: Request, payload: UnitCreatePayload):
    """Create a reusable unit owned by the calling teacher."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    sub = _current_sub(user)
    repo = _get_repo()
    unit_type = str(payload.unit_type or "").strip().lower()
    if unit_type == "modular":
        repo_error = _require_modular_repo_methods(repo, *_MODULAR_UNIT_CREATE_REQUIRED_METHODS)
        if repo_error:
            return repo_error
    try:
        unit = repo.create_unit(
            title=payload.title or "",
            summary=payload.summary,
            author_id=sub,
            unit_type=payload.unit_type,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail in {"invalid_title", "invalid_summary", "invalid_unit_type"}:
            return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
        return _private_error({"error": "bad_request"}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    return _json_private(_serialize_unit(unit), status_code=201)


@teaching_units_router.get("/api/teaching/units/{unit_id}")
async def get_unit(request: Request, unit_id: str):
    """Get a learning unit by id for its author."""

    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        unit = repo.get_unit_for_author(unit_id, sub)
    except TeachingRepositoryUnavailable:
        raise
    except Exception:
        unit = repo.get_unit_for_author(unit_id, sub)
    if not unit:
        return _private_error({"error": "not_found"}, status_code=404)
    return _json_private(_serialize_unit(unit), status_code=200)


@teaching_units_router.patch("/api/teaching/units/{unit_id}")
async def update_unit(request: Request, unit_id: str, payload: UnitUpdatePayload):
    """Update metadata of a unit owned by the current teacher."""

    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    updates = payload.model_dump(mode="python", exclude_unset=True)
    if not updates:
        return JSONResponse({"error": "bad_request", "detail": "empty_payload"}, status_code=400)
    try:
        updated = repo.update_unit_owned(unit_id, sub, **updates)
    except ValueError as exc:
        return JSONResponse({"error": "bad_request", "detail": str(exc)}, status_code=400)
    if not updated:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return _json_private(_serialize_unit(updated), status_code=200)


@teaching_units_router.delete("/api/teaching/units/{unit_id}")
async def delete_unit(request: Request, unit_id: str):
    """Delete a unit owned by the current teacher, including storage cleanup."""

    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        storage_objects = _current_collect_unit_delete_storage_objects()(repo, unit_id=unit_id)
        _current_delete_unit_storage_objects()(storage_objects)
        deleted = repo.delete_unit_owned(unit_id, sub)
    except TeachingRepositoryUnavailable:
        raise
    except RuntimeError as exc:
        detail = str(exc) or "storage_delete_failed"
        if detail in {"storage_adapter_not_configured", "storage_metadata_unavailable"}:
            return JSONResponse(
                {"error": "service_unavailable", "detail": "storage_adapter_unavailable"},
                status_code=503,
            )
        return JSONResponse(
            {"error": "bad_gateway", "detail": "storage_delete_failed"},
            status_code=502,
        )
    except Exception:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if not deleted:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})
