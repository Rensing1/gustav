"""Teaching unit section routes.

Why:
    Section endpoints are part of the authoring workflow and should own their
    HTTP behavior directly instead of delegating through the large `teaching.py`
    adapter.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from backend.teaching.errors import TeachingRepositoryUnavailable
from backend.web.routes import teaching_guards
from backend.web.routes.teaching import _get_repo
from backend.web.routes.teaching_payloads import SectionCreatePayload, SectionReorderPayload, SectionUpdatePayload
from backend.web.routes.teaching_serialization import _serialize_section
from backend.web.routes.teaching_shared import (
    _current_sub,
    _is_uuid_like,
    _json_private,
    _require_teacher,
)


teaching_unit_sections_router = APIRouter(tags=["Teaching"])


@teaching_unit_sections_router.get("/api/teaching/units/{unit_id}/sections")
async def list_sections(request: Request, unit_id: str):
    """List sections of a learning unit for the authoring teacher."""

    user, error = _require_teacher(request)
    if error:
        return error
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        items = _get_repo().list_sections_for_author(unit_id, sub)
    except TeachingRepositoryUnavailable:
        raise
    except Exception:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return _json_private([_serialize_section(section) for section in items], status_code=200)


@teaching_unit_sections_router.post("/api/teaching/units/{unit_id}/sections")
async def create_section(request: Request, unit_id: str, payload: SectionCreatePayload):
    """Create a section in a unit; new sections append at the next position."""

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
        section = _get_repo().create_section(unit_id, payload.title or "", sub)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_title"}, status_code=400)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return JSONResponse(content=_serialize_section(section), status_code=201)


@teaching_unit_sections_router.patch("/api/teaching/units/{unit_id}/sections/{section_id}")
async def update_section(
    request: Request,
    unit_id: str,
    section_id: str,
    payload: SectionUpdatePayload,
):
    """Update a section title for the authoring teacher."""

    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id) or not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_path_params"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    updates = payload.model_dump(mode="python", exclude_unset=True)
    if not updates:
        return JSONResponse({"error": "bad_request", "detail": "empty_payload"}, status_code=400)
    try:
        updated = repo.update_section_title(unit_id, section_id, updates.get("title"), sub)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_title"}, status_code=400)
    if not updated:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse(content=_serialize_section(updated), status_code=200)


@teaching_unit_sections_router.delete("/api/teaching/units/{unit_id}/sections/{section_id}")
async def delete_section(request: Request, unit_id: str, section_id: str):
    """Delete a section and resequence remaining positions."""

    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id) or not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_path_params"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    deleted = repo.delete_section(unit_id, section_id, sub)
    if not deleted:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@teaching_unit_sections_router.post("/api/teaching/units/{unit_id}/sections/reorder")
async def reorder_sections(request: Request, unit_id: str, payload: SectionReorderPayload):
    """Reorder sections transactionally to positions 1..n as provided."""

    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    ids = payload.section_ids
    if not isinstance(ids, list):
        return JSONResponse({"error": "bad_request", "detail": "section_ids_must_be_array"}, status_code=400)
    if len(ids) == 0:
        return JSONResponse({"error": "bad_request", "detail": "empty_section_ids"}, status_code=400)
    if len(ids) != len(set(ids)):
        return JSONResponse({"error": "bad_request", "detail": "duplicate_section_ids"}, status_code=400)
    if any(not _is_uuid_like(section_id) for section_id in ids):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_ids"}, status_code=400)
    try:
        ordered = repo.reorder_unit_sections_owned(unit_id, sub, ids)
    except ValueError as exc:
        return JSONResponse({"error": "bad_request", "detail": str(exc)}, status_code=400)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return JSONResponse(content=[_serialize_section(section) for section in ordered], status_code=200)
