"""Teaching unit material routes.

Why:
    Material authoring has its own HTTP surface for Markdown resources, file
    upload intents, finalized file materials, module-backed material aliases,
    and file download URLs. Keeping those handlers here reduces the Teaching
    adapter hotspot without changing the existing response contracts.
"""

from __future__ import annotations

import importlib
import logging
import re
import sys as _sys
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from backend.teaching.storage import NullStorageAdapter
from backend.web.routes import teaching_authoring, teaching_guards
from backend.web.routes.teaching_payloads import (
    MaterialCreatePayload,
    MaterialFinalizePayload,
    MaterialReorderPayload,
    MaterialUpdatePayload,
    MaterialUploadIntentPayload,
)
from backend.web.routes.teaching_serialization import _serialize_material
from backend.web.routes.teaching_shared import (
    _current_sub,
    _is_uuid_like,
    _json_private,
    _require_teacher,
)


teaching_unit_materials_router = APIRouter(tags=["Teaching"])
logger = logging.getLogger("gustav.web.teaching.materials")

# These globals are intentionally present so teaching.set_storage_adapter() can
# retarget already-registered routes. When unset, the router reads the current
# values from backend.web.routes.teaching dynamically.
STORAGE_ADAPTER = None
MATERIAL_FILE_SETTINGS = None
_STORAGE_ADAPTER_OVERRIDE_ACTIVE = None
_BOUND_TEACHING_MODULE = _sys.modules.get("backend.web.routes.teaching")


def _teaching_module():
    module = _BOUND_TEACHING_MODULE or _sys.modules.get("backend.web.routes.teaching")
    if module is None:  # pragma: no cover - defensive import fallback
        module = importlib.import_module("backend.web.routes.teaching")
    return module


def _get_repo():
    """Resolve the active Teaching repo provider after tests reload or monkeypatch it."""

    return _teaching_module()._get_repo()


def _get_materials_service():
    """Resolve the active MaterialsService provider from the Teaching facade."""

    return _teaching_module()._get_materials_service()


def _storage_adapter():
    """Return the current storage adapter, preferring route-global sync updates."""

    return STORAGE_ADAPTER if STORAGE_ADAPTER is not None else _teaching_module().STORAGE_ADAPTER


def _material_file_settings():
    """Return material storage settings, preferring route-global sync updates."""

    facade_settings = getattr(_teaching_module(), "MATERIAL_FILE_SETTINGS", None)
    if facade_settings is not None:
        return facade_settings
    if MATERIAL_FILE_SETTINGS is not None:
        return MATERIAL_FILE_SETTINGS
    return _teaching_module().MATERIAL_FILE_SETTINGS


def _storage_override_active() -> bool:
    """Return whether a test or runtime explicitly replaced the storage adapter."""

    if _STORAGE_ADAPTER_OVERRIDE_ACTIVE is not None:
        return bool(_STORAGE_ADAPTER_OVERRIDE_ACTIVE)
    return bool(_teaching_module()._STORAGE_ADAPTER_OVERRIDE_ACTIVE)


def _wire_storage_if_configured():
    """Retry lazy Supabase storage wiring through the Teaching facade."""

    wire_storage = getattr(_teaching_module(), "_wire_storage", None)
    if callable(wire_storage):
        wire_storage()


@teaching_unit_materials_router.get("/api/teaching/units/{unit_id}/sections/{section_id}/materials")
async def list_section_materials(request: Request, unit_id: str, section_id: str):
    """List markdown materials of a section for its author."""

    user, error = _require_teacher(request)
    if error:
        return error
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        items = _get_materials_service().list_markdown_materials(unit_id, section_id, sub)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return _json_private([_serialize_material(m) for m in items], status_code=200)


@teaching_unit_materials_router.post("/api/teaching/units/{unit_id}/sections/{section_id}/materials")
async def create_section_material(
    request: Request,
    unit_id: str,
    section_id: str,
    payload: MaterialCreatePayload,
):
    """Create a markdown material in a section."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        _get_materials_service().ensure_section_owned(unit_id, section_id, sub)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    title = payload.title or ""
    if not title or len(title) > 200:
        return JSONResponse({"error": "bad_request", "detail": "invalid_title"}, status_code=400)
    body = payload.body_md
    if body is None or not isinstance(body, str):
        return JSONResponse({"error": "bad_request", "detail": "invalid_body_md"}, status_code=400)
    try:
        material = _get_materials_service().create_markdown_material(
            unit_id,
            section_id,
            sub,
            title=title,
            body_md=body,
        )
    except ValueError as exc:
        return JSONResponse({"error": "bad_request", "detail": str(exc)}, status_code=400)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return _json_private(_serialize_material(material), status_code=201)


@teaching_unit_materials_router.patch("/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}")
async def update_section_material(
    request: Request,
    unit_id: str,
    section_id: str,
    material_id: str,
    payload: MaterialUpdatePayload,
):
    """Update mutable fields of a markdown material."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    if not _is_uuid_like(material_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_material_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        _get_materials_service().ensure_section_owned(unit_id, section_id, sub)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    if _get_materials_service().get_material_owned(unit_id, section_id, material_id, sub) is None:
        return JSONResponse({"error": "not_found"}, status_code=404)

    raw_updates = payload.model_dump(mode="python", exclude_unset=True)
    fields_set = payload.model_fields_set
    if not fields_set:
        return JSONResponse({"error": "bad_request", "detail": "empty_payload"}, status_code=400)

    kwargs = {}
    if "title" in fields_set:
        if raw_updates.get("title") is None:
            return JSONResponse({"error": "bad_request", "detail": "invalid_title"}, status_code=400)
        title_val = raw_updates.get("title") or ""
        if not title_val or len(title_val) > 200:
            return JSONResponse({"error": "bad_request", "detail": "invalid_title"}, status_code=400)
        kwargs["title"] = title_val
    if "body_md" in fields_set:
        body_val = raw_updates.get("body_md")
        if body_val is None or not isinstance(body_val, str):
            return JSONResponse({"error": "bad_request", "detail": "invalid_body_md"}, status_code=400)
        kwargs["body_md"] = body_val
    if "alt_text" in fields_set:
        alt_val = raw_updates.get("alt_text")
        if alt_val is not None and not isinstance(alt_val, str):
            return JSONResponse({"error": "bad_request", "detail": "invalid_alt_text"}, status_code=400)
        normalized_alt = (alt_val or "").strip() if isinstance(alt_val, str) else None
        kwargs["alt_text"] = normalized_alt or None
    try:
        updated = _get_materials_service().update_material(
            unit_id,
            section_id,
            material_id,
            sub,
            **kwargs,
        )
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        if detail not in {"invalid_title", "invalid_body_md", "invalid_alt_text"}:
            detail = "invalid_input"
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return JSONResponse(content=_serialize_material(updated), status_code=200)


@teaching_unit_materials_router.delete("/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}")
async def delete_section_material(request: Request, unit_id: str, section_id: str, material_id: str):
    """Delete a material in a section."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    if not _is_uuid_like(material_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_material_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        _get_materials_service().ensure_section_owned(unit_id, section_id, sub)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    material_obj = _get_materials_service().get_material_owned(unit_id, section_id, material_id, sub)
    if material_obj is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    material_snapshot = _serialize_material(material_obj)
    storage_key = material_snapshot.get("storage_key")
    material_kind = material_snapshot.get("kind")
    if material_kind == "file" and storage_key:
        try:
            delete_fn = getattr(_storage_adapter(), "delete_object", None)
            if callable(delete_fn):
                delete_fn(
                    bucket=_material_file_settings().storage_bucket,
                    key=storage_key,
                )
        except RuntimeError as exc:  # pragma: no cover - defensive log path
            if str(exc) == "storage_adapter_not_configured":
                logger.error("Storage adapter unavailable during delete for material %s", material_id)
                return JSONResponse({"error": "service_unavailable"}, status_code=503)
            raise
        except Exception:  # pragma: no cover - log unexpected storage failures
            logger.exception("Failed deleting storage object for material %s", material_id)
            return JSONResponse(
                {"error": "bad_gateway", "detail": "storage_delete_failed"},
                status_code=502,
            )
    try:
        _get_materials_service().delete_material(unit_id, section_id, material_id, sub)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@teaching_unit_materials_router.post("/api/teaching/units/{unit_id}/sections/{section_id}/materials/upload-intents")
async def create_section_material_upload_intent(
    request: Request,
    unit_id: str,
    section_id: str,
    payload: MaterialUploadIntentPayload,
):
    """Create a presigned upload intent for a file material."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    if isinstance(_storage_adapter(), NullStorageAdapter) and not _storage_override_active():
        try:
            _wire_storage_if_configured()
        except Exception:
            pass
    try:
        intent = _get_materials_service().create_file_upload_intent(
            unit_id,
            section_id,
            sub,
            filename=payload.filename,
            mime_type=payload.mime_type,
            size_bytes=int(payload.size_bytes),
            storage=_storage_adapter(),
        )
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        if detail not in {"mime_not_allowed", "size_exceeded", "invalid_filename"}:
            detail = "invalid_input"
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400)
    except RuntimeError as exc:
        if str(exc) == "storage_adapter_not_configured":
            return JSONResponse({"error": "service_unavailable"}, status_code=503)
        raise
    return JSONResponse(content=intent, status_code=200)


@teaching_unit_materials_router.post("/api/teaching/units/{unit_id}/sections/{section_id}/materials/finalize")
async def finalize_section_material_upload(
    request: Request,
    unit_id: str,
    section_id: str,
    payload: MaterialFinalizePayload,
):
    """Finalize an upload intent and persist the file material."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    if not _is_uuid_like(payload.intent_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_intent_id"}, status_code=400)
    normalized_sha = (payload.sha256 or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized_sha):
        return JSONResponse({"error": "bad_request", "detail": "checksum_mismatch"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        material, created = _get_materials_service().finalize_file_material(
            unit_id,
            section_id,
            sub,
            intent_id=payload.intent_id,
            title=payload.title,
            sha256=payload.sha256,
            alt_text=payload.alt_text,
            storage=_storage_adapter(),
        )
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        if detail not in {
            "intent_expired",
            "checksum_mismatch",
            "invalid_title",
            "mime_not_allowed",
            "invalid_alt_text",
        }:
            detail = "invalid_input"
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400)
    except RuntimeError as exc:
        if str(exc) == "storage_adapter_not_configured":
            return JSONResponse({"error": "service_unavailable"}, status_code=503)
        raise
    status_code = 201 if created else 200
    return JSONResponse(content=_serialize_material(material), status_code=status_code)


@teaching_unit_materials_router.post("/api/teaching/units/{unit_id}/modules/{module_id}/materials")
async def create_module_material(
    request: Request,
    unit_id: str,
    module_id: str,
    payload: MaterialCreatePayload,
):
    """Create a material in a module-backed section."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        repo_provider=_get_repo,
    )
    if error:
        return error
    return await create_section_material(request, unit_id, str(section_id), payload)


@teaching_unit_materials_router.patch("/api/teaching/units/{unit_id}/modules/{module_id}/materials/{material_id}")
async def update_module_material(
    request: Request,
    unit_id: str,
    module_id: str,
    material_id: str,
    payload: MaterialUpdatePayload,
):
    """Update a material in a module-backed section."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        repo_provider=_get_repo,
    )
    if error:
        return error
    return await update_section_material(request, unit_id, str(section_id), material_id, payload)


@teaching_unit_materials_router.delete("/api/teaching/units/{unit_id}/modules/{module_id}/materials/{material_id}")
async def delete_module_material(
    request: Request,
    unit_id: str,
    module_id: str,
    material_id: str,
):
    """Delete a material in a module-backed section."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        repo_provider=_get_repo,
    )
    if error:
        return error
    return await delete_section_material(request, unit_id, str(section_id), material_id)


@teaching_unit_materials_router.post("/api/teaching/units/{unit_id}/modules/{module_id}/materials/reorder")
async def reorder_module_materials(
    request: Request,
    unit_id: str,
    module_id: str,
    payload: MaterialReorderPayload,
):
    """Reorder materials in a module-backed section."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        repo_provider=_get_repo,
    )
    if error:
        return error
    return await reorder_section_materials(request, unit_id, str(section_id), payload)


@teaching_unit_materials_router.post("/api/teaching/units/{unit_id}/modules/{module_id}/materials/upload-intents")
async def create_module_material_upload_intent(
    request: Request,
    unit_id: str,
    module_id: str,
    payload: MaterialUploadIntentPayload,
):
    """Create a file-material upload intent in a module-backed section."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        repo_provider=_get_repo,
    )
    if error:
        return error
    return await create_section_material_upload_intent(request, unit_id, str(section_id), payload)


@teaching_unit_materials_router.post("/api/teaching/units/{unit_id}/modules/{module_id}/materials/finalize")
async def finalize_module_material_upload(
    request: Request,
    unit_id: str,
    module_id: str,
    payload: MaterialFinalizePayload,
):
    """Finalize a file-material upload in a module-backed section."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        repo_provider=_get_repo,
    )
    if error:
        return error
    return await finalize_section_material_upload(request, unit_id, str(section_id), payload)


@teaching_unit_materials_router.get(
    "/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}/download-url"
)
async def get_section_material_download_url(
    request: Request,
    unit_id: str,
    section_id: str,
    material_id: str,
    disposition: Optional[str] = None,
):
    """Generate a short-lived download URL for a file material."""

    user, error = _require_teacher(request)
    if error:
        return error
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    if not _is_uuid_like(material_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_material_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    normalized_disposition = (disposition or "attachment").strip().lower()
    if normalized_disposition not in {"inline", "attachment"}:
        return JSONResponse({"error": "bad_request", "detail": "invalid_disposition"}, status_code=400)
    try:
        payload = _get_materials_service().generate_file_download_url(
            unit_id,
            section_id,
            material_id,
            sub,
            disposition=normalized_disposition,
            storage=_storage_adapter(),
        )
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        if detail not in {"invalid_disposition"}:
            detail = "invalid_input"
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400)
    except RuntimeError as exc:
        if str(exc) == "storage_adapter_not_configured":
            return JSONResponse({"error": "service_unavailable"}, status_code=503)
        raise
    return JSONResponse(content=payload, status_code=200, headers={"Cache-Control": "private, no-store"})


@teaching_unit_materials_router.post("/api/teaching/units/{unit_id}/sections/{section_id}/materials/reorder")
async def reorder_section_materials(
    request: Request,
    unit_id: str,
    section_id: str,
    payload: MaterialReorderPayload,
):
    """Reorder materials within a section."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    ids = payload.material_ids
    if not isinstance(ids, list):
        return JSONResponse({"error": "bad_request", "detail": "material_ids_must_be_array"}, status_code=400)
    if len(ids) == 0:
        return JSONResponse({"error": "bad_request", "detail": "empty_material_ids"}, status_code=400)
    if len(ids) != len(set(ids)):
        return JSONResponse({"error": "bad_request", "detail": "duplicate_material_ids"}, status_code=400)
    if any(not _is_uuid_like(mid) for mid in ids):
        return JSONResponse({"error": "bad_request", "detail": "invalid_material_ids"}, status_code=400)
    try:
        _get_materials_service().ensure_section_owned(unit_id, section_id, sub)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    try:
        ordered = _get_materials_service().reorder_markdown_materials(unit_id, section_id, sub, ids)
    except ValueError as exc:
        return JSONResponse({"error": "bad_request", "detail": str(exc)}, status_code=400)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return JSONResponse(content=[_serialize_material(m) for m in ordered], status_code=200)
