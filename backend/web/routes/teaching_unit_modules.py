"""Teaching unit phase and module routes.

Why:
    Modular units have their own authoring surface for phases, graph nodes, and
    dependency edges. Keeping these HTTP handlers in a focused router makes the
    large Teaching adapter easier to read while shared repo and guard providers
    are still being extracted.
"""

from __future__ import annotations

import importlib
import sys as _sys

from fastapi import APIRouter, Request
from fastapi.responses import Response

from backend.teaching.errors import TeachingRepositoryUnavailable
from backend.web.routes import teaching_guards
from backend.web.routes.teaching import (
    _UNSET,
    _list_unit_modules_for_author_compat,
    _require_modular_repo_methods,
    _validate_uuid_id_list,
)
from backend.web.routes.teaching_authoring import _get_unit_module_section_id_for_author
from backend.web.routes.teaching_payloads import (
    UnitModuleCreatePayload,
    UnitModuleEdgePayload,
    UnitModuleReorderPayload,
    UnitModuleUpdatePayload,
    UnitPhaseCreatePayload,
    UnitPhaseReorderPayload,
    UnitPhaseUpdatePayload,
)
from backend.web.routes.teaching_serialization import (
    _serialize_unit_graph_edge,
    _serialize_unit_module,
    _serialize_unit_phase_public,
)
from backend.web.routes.teaching_shared import (
    _current_sub,
    _is_uuid_like,
    _json_private,
    _private_error,
    _require_teacher,
)
from backend.web.routes.teaching_validation import canonical_uuid as _canonical_uuid


teaching_unit_modules_router = APIRouter(tags=["Teaching"])
_BOUND_TEACHING_MODULE = _sys.modules.get("backend.web.routes.teaching")


def _get_repo():
    """Resolve the active Teaching repo provider after tests reload or monkeypatch it."""

    teaching_module = _BOUND_TEACHING_MODULE or _sys.modules.get("backend.web.routes.teaching")
    if teaching_module is None:  # pragma: no cover - defensive import fallback
        teaching_module = importlib.import_module("backend.web.routes.teaching")
    return teaching_module._get_repo()


@teaching_unit_modules_router.get("/api/teaching/units/{unit_id}/phases")
async def list_unit_phases(request: Request, unit_id: str):
    """List phases of a modular unit (author only)."""

    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(repo, "list_unit_phases_for_author")
    if repo_error:
        return repo_error
    try:
        items = repo.list_unit_phases_for_author(unit_id, sub)
    except ValueError as exc:
        detail = str(exc) or "bad_request"
        if detail == "invalid_unit_type":
            return _private_error({"error": "bad_request", "detail": "invalid_unit_type"}, status_code=400)
        return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    except TeachingRepositoryUnavailable:
        raise
    except Exception:
        raise
    return _json_private([_serialize_unit_phase_public(p) for p in items], status_code=200)


@teaching_unit_modules_router.post("/api/teaching/units/{unit_id}/phases")
async def create_unit_phase(request: Request, unit_id: str, payload: UnitPhaseCreatePayload):
    """Create a phase in a modular unit (author only); appends at the next position."""

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
    repo_error = _require_modular_repo_methods(repo, "create_unit_phase")
    if repo_error:
        return repo_error
    title = payload.title or ""
    try:
        phase = repo.create_unit_phase(unit_id, title, sub)
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        if detail in {"invalid_unit_type", "invalid_title"}:
            return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
        return _private_error({"error": "bad_request", "detail": "invalid_input"}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    return _json_private(_serialize_unit_phase_public(phase), status_code=201, vary_origin=True)


@teaching_unit_modules_router.patch("/api/teaching/units/{unit_id}/phases/{phase_id}")
async def update_unit_phase(
    request: Request,
    unit_id: str,
    phase_id: str,
    payload: UnitPhaseUpdatePayload,
):
    """Rename a phase in a modular unit (author only)."""

    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id) or not _is_uuid_like(phase_id):
        return _private_error({"error": "bad_request", "detail": "invalid_path_params"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(repo, "update_unit_phase_title")
    if repo_error:
        return repo_error
    updates = payload.model_dump(mode="python", exclude_unset=True)
    if not updates:
        return _private_error({"error": "bad_request", "detail": "empty_payload"}, status_code=400)
    try:
        updated = repo.update_unit_phase_title(unit_id, phase_id, updates.get("title"), sub)
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        if detail in {"invalid_unit_type", "invalid_title"}:
            return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
        return _private_error({"error": "bad_request", "detail": "invalid_input"}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    if not updated:
        return _private_error({"error": "not_found"}, status_code=404)
    return _json_private(_serialize_unit_phase_public(updated), status_code=200, vary_origin=True)


@teaching_unit_modules_router.delete("/api/teaching/units/{unit_id}/phases/{phase_id}")
async def delete_unit_phase(request: Request, unit_id: str, phase_id: str):
    """Delete a phase (and all modules/edges/content inside it) (author only)."""

    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(phase_id):
        return _private_error({"error": "bad_request", "detail": "invalid_phase_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(repo, "delete_unit_phase_for_author")
    if repo_error:
        return repo_error
    try:
        deleted = repo.delete_unit_phase_for_author(unit_id=unit_id, phase_id=phase_id, author_id=sub)
    except ValueError as exc:
        detail = str(exc) or "bad_request"
        if detail == "invalid_unit_type":
            return _private_error({"error": "bad_request", "detail": "invalid_unit_type"}, status_code=400)
        return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    if not deleted:
        return _private_error({"error": "not_found"}, status_code=404)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@teaching_unit_modules_router.post("/api/teaching/units/{unit_id}/phases/reorder")
async def reorder_unit_phases(request: Request, unit_id: str, payload: UnitPhaseReorderPayload):
    """Reorder phases (author only) transactionally to positions 1..n as provided."""

    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(repo, "reorder_unit_phases_owned")
    if repo_error:
        return repo_error
    ids, ids_error = _validate_uuid_id_list(
        payload.phase_ids,
        array_detail="phase_ids_must_be_array",
        empty_detail="empty_phase_ids",
        duplicate_detail="duplicate_phase_ids",
        invalid_detail="invalid_phase_ids",
    )
    if ids_error:
        return ids_error
    try:
        ordered = repo.reorder_unit_phases_owned(unit_id, sub, ids)
    except ValueError as exc:
        detail = str(exc) or "bad_request"
        return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
    except LookupError:
        return _private_error({"error": "not_found"}, status_code=404)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    except TeachingRepositoryUnavailable:
        raise
    except Exception as exc:
        sqlstate = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
        if sqlstate == "23514":
            return _private_error(
                {"error": "bad_request", "detail": "edge_constraint_violation"},
                status_code=400,
            )
        raise
    return _json_private([_serialize_unit_phase_public(p) for p in ordered], status_code=200, vary_origin=True)


@teaching_unit_modules_router.get("/api/teaching/units/{unit_id}/modules/graph")
async def get_unit_modules_graph(request: Request, unit_id: str):
    """Return the authoring graph payload for a modular unit (author only)."""

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
    repo_error = _require_modular_repo_methods(
        repo,
        "list_unit_phases_for_author",
        "list_unit_modules_for_author",
        "list_unit_module_edges_for_author",
    )
    if repo_error:
        return repo_error
    try:
        phases = repo.list_unit_phases_for_author(unit_id, sub)
        modules = repo.list_unit_modules_for_author(unit_id=unit_id, author_id=sub)
        edges = repo.list_unit_module_edges_for_author(unit_id=unit_id, author_id=sub)
    except ValueError as exc:
        detail = str(exc) or "bad_request"
        if detail == "invalid_unit_type":
            return _private_error({"error": "bad_request", "detail": "invalid_unit_type"}, status_code=400)
        return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
    except LookupError:
        return _private_error({"error": "not_found"}, status_code=404)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)

    payload = {
        "unit_id": unit_id,
        "phases": [_serialize_unit_phase_public(p) for p in phases],
        "modules": [_serialize_unit_module(m) for m in modules],
        "edges": [_serialize_unit_graph_edge(e) for e in edges],
    }
    return _json_private(payload, status_code=200)


@teaching_unit_modules_router.get("/api/teaching/units/{unit_id}/modules/{module_id}/content-target")
async def get_unit_module_content_target(request: Request, unit_id: str, module_id: str):
    """Return the backing section id for a modular unit module."""

    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(module_id):
        return _private_error({"error": "bad_request", "detail": "invalid_module_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    if not hasattr(repo, "get_unit_module_for_author"):
        return _private_error({"error": "service_unavailable", "detail": "modular_repo_unavailable"}, status_code=503)
    try:
        section_id = _get_unit_module_section_id_for_author(repo, unit_id=unit_id, module_id=module_id, author_id=sub)
    except LookupError:
        return _private_error({"error": "not_found"}, status_code=404)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    if not section_id:
        return _private_error({"error": "not_found"}, status_code=404)
    return _json_private({"module_id": str(module_id), "section_id": str(section_id)}, status_code=200)


@teaching_unit_modules_router.post("/api/teaching/units/{unit_id}/modules")
async def create_unit_module(request: Request, unit_id: str, payload: UnitModuleCreatePayload):
    """Create a module (graph node) inside a phase (author only)."""

    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(repo, "create_unit_module_for_author")
    if repo_error:
        return repo_error
    title = payload.title or ""
    phase_id = payload.phase_id or ""
    if not _is_uuid_like(phase_id):
        return _private_error({"error": "bad_request", "detail": "invalid_phase_id"}, status_code=400)
    if not title or len(title) > 200:
        return _private_error({"error": "bad_request", "detail": "invalid_title"}, status_code=400)
    try:
        created = repo.create_unit_module_for_author(unit_id=unit_id, phase_id=phase_id, title=title, author_id=sub)
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        if detail in {"invalid_unit_type", "invalid_title"}:
            return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
        return _private_error({"error": "bad_request", "detail": "invalid_input"}, status_code=400)
    except LookupError:
        return _private_error({"error": "not_found"}, status_code=404)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    return _json_private(_serialize_unit_module(created), status_code=201, vary_origin=True)


@teaching_unit_modules_router.post("/api/teaching/units/{unit_id}/modules/edges")
async def create_unit_module_edge(request: Request, unit_id: str, payload: UnitModuleEdgePayload):
    """Create a directed dependency edge within a modular unit (author only)."""

    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(
        repo,
        "list_unit_modules_for_author",
        "create_unit_module_edge_for_author",
    )
    if repo_error:
        return repo_error

    from_id = payload.from_module_id or ""
    to_id = payload.to_module_id or ""
    if not _is_uuid_like(from_id) or not _is_uuid_like(to_id):
        return _private_error({"error": "bad_request", "detail": "invalid_module_ids"}, status_code=400)
    from_id = _canonical_uuid(from_id)
    to_id = _canonical_uuid(to_id)
    try:
        modules = _list_unit_modules_for_author_compat(repo, unit_id=unit_id, author_id=sub)
    except ValueError as exc:
        detail = str(exc) or "bad_request"
        if detail == "invalid_unit_type":
            return _private_error({"error": "bad_request", "detail": "invalid_unit_type"}, status_code=400)
        return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    except LookupError:
        return _private_error({"error": "not_found"}, status_code=404)
    module_ids: set[str] = set()
    for item in modules or []:
        raw_id = str((item or {}).get("id")) if isinstance(item, dict) else str(getattr(item, "id", ""))
        if _is_uuid_like(raw_id):
            module_ids.add(_canonical_uuid(raw_id))
    if from_id not in module_ids or to_id not in module_ids:
        return _private_error({"error": "not_found"}, status_code=404)
    try:
        created = repo.create_unit_module_edge_for_author(
            unit_id=unit_id, from_module_id=from_id, to_module_id=to_id, author_id=sub
        )
    except ValueError as exc:
        detail = str(exc) or "bad_request"
        if detail == "invalid_unit_type":
            return _private_error({"error": "bad_request", "detail": "invalid_unit_type"}, status_code=400)
        return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    except TeachingRepositoryUnavailable:
        raise
    except Exception as exc:
        sqlstate = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
        if sqlstate == "23514":
            return _private_error({"error": "bad_request", "detail": "edge_constraint_violation"}, status_code=400)
        if sqlstate == "23503":
            return _private_error({"error": "not_found"}, status_code=404)
        if sqlstate == "23505":
            return _private_error({"error": "conflict", "detail": "duplicate_edge"}, status_code=409)
        raise
    return _json_private(_serialize_unit_graph_edge(created), status_code=201, vary_origin=True)


def _delete_unit_module_edge_common(*, request: Request, unit_id: str, from_id: str, to_id: str):
    """Delete a directed dependency edge within a modular unit (author only)."""

    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(repo, "delete_unit_module_edge_for_author")
    if repo_error:
        return repo_error

    if not _is_uuid_like(from_id) or not _is_uuid_like(to_id):
        return _private_error({"error": "bad_request", "detail": "invalid_module_ids"}, status_code=400)
    try:
        deleted = repo.delete_unit_module_edge_for_author(
            unit_id=unit_id,
            from_module_id=from_id,
            to_module_id=to_id,
            author_id=sub,
        )
    except ValueError:
        return _private_error({"error": "bad_request", "detail": "invalid_unit_type"}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    if not deleted:
        return _private_error({"error": "not_found"}, status_code=404)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


_LEGACY_EDGE_DELETE_SUNSET_HTTP = "Tue, 30 Jun 2026 23:59:59 GMT"
_LEGACY_EDGE_DELETE_SUCCESSOR_LINK_TEMPLATE = (
    '</api/teaching/units/{unit_id}/modules/{from_module_id}/edges/{to_module_id}>; rel="successor-version"'
)


def _legacy_edge_delete_successor_link(*, unit_id: str, from_module_id: str, to_module_id: str) -> str:
    """Build the successor Link header for the path-based delete endpoint."""

    if not (_is_uuid_like(unit_id) and _is_uuid_like(from_module_id) and _is_uuid_like(to_module_id)):
        return _LEGACY_EDGE_DELETE_SUCCESSOR_LINK_TEMPLATE
    return (
        f'</api/teaching/units/{_canonical_uuid(unit_id)}/modules/'
        f'{_canonical_uuid(from_module_id)}/edges/{_canonical_uuid(to_module_id)}>; rel="successor-version"'
    )


@teaching_unit_modules_router.delete("/api/teaching/units/{unit_id}/modules/edges")
async def delete_unit_module_edge(request: Request, unit_id: str, payload: UnitModuleEdgePayload):
    """Delete a dependency edge using request-body module ids (author only)."""

    response = _delete_unit_module_edge_common(
        request=request,
        unit_id=unit_id,
        from_id=str(payload.from_module_id or ""),
        to_id=str(payload.to_module_id or ""),
    )
    if int(getattr(response, "status_code", 0)) == 204:
        response.headers.setdefault("Deprecation", "true")
        response.headers.setdefault("Sunset", _LEGACY_EDGE_DELETE_SUNSET_HTTP)
        response.headers.setdefault(
            "Link",
            _legacy_edge_delete_successor_link(
                unit_id=unit_id,
                from_module_id=str(payload.from_module_id or ""),
                to_module_id=str(payload.to_module_id or ""),
            ),
        )
    return response


@teaching_unit_modules_router.delete("/api/teaching/units/{unit_id}/modules/{from_module_id}/edges/{to_module_id}")
async def delete_unit_module_edge_by_path(
    request: Request,
    unit_id: str,
    from_module_id: str,
    to_module_id: str,
):
    """Delete a dependency edge using path params (author only)."""

    return _delete_unit_module_edge_common(
        request=request,
        unit_id=unit_id,
        from_id=str(from_module_id or ""),
        to_id=str(to_module_id or ""),
    )


@teaching_unit_modules_router.patch("/api/teaching/units/{unit_id}/modules/{module_id}")
async def update_unit_module(
    request: Request,
    unit_id: str,
    module_id: str,
    payload: UnitModuleUpdatePayload,
):
    """Update module settings (author only)."""

    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(module_id):
        return _private_error({"error": "bad_request", "detail": "invalid_module_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(repo, "update_unit_module_owned")
    if repo_error:
        return repo_error
    title_provided = "title" in payload.model_fields_set
    k_provided = "required_prereq_count" in payload.model_fields_set
    if not (title_provided or k_provided):
        return _private_error({"error": "bad_request", "detail": "empty_payload"}, status_code=400)

    title = payload.title if title_provided else _UNSET
    if title is not _UNSET and (title is None or (not str(title).strip()) or len(str(title).strip()) > 200):
        return _private_error({"error": "bad_request", "detail": "invalid_title"}, status_code=400)

    k = payload.required_prereq_count if k_provided else _UNSET
    if k is not _UNSET:
        if k is None or isinstance(k, bool) or (not isinstance(k, int)) or int(k) < 0:
            return _private_error(
                {"error": "bad_request", "detail": "invalid_required_prereq_count"},
                status_code=400,
            )
    try:
        update_kwargs: dict[str, object] = {}
        if title_provided:
            update_kwargs["title"] = title
        if k_provided:
            update_kwargs["required_prereq_count"] = k
        updated = repo.update_unit_module_owned(
            unit_id=unit_id,
            module_id=module_id,
            author_id=sub,
            **update_kwargs,
        )
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        if detail in {"invalid_unit_type", "invalid_title", "invalid_required_prereq_count"}:
            return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
        return _private_error({"error": "bad_request", "detail": "invalid_input"}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    if not updated:
        return _private_error({"error": "not_found"}, status_code=404)
    return _json_private(_serialize_unit_module(updated), status_code=200, vary_origin=True)


@teaching_unit_modules_router.delete("/api/teaching/units/{unit_id}/modules/{module_id}")
async def delete_unit_module(request: Request, unit_id: str, module_id: str):
    """Delete a module and its backing content (author only)."""

    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(module_id):
        return _private_error({"error": "bad_request", "detail": "invalid_module_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(repo, "delete_unit_module_for_author")
    if repo_error:
        return repo_error
    try:
        deleted = repo.delete_unit_module_for_author(unit_id=unit_id, module_id=module_id, author_id=sub)
    except ValueError as exc:
        detail = str(exc) or "bad_request"
        if detail == "invalid_unit_type":
            return _private_error({"error": "bad_request", "detail": "invalid_unit_type"}, status_code=400)
        return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    if not deleted:
        return _private_error({"error": "not_found"}, status_code=404)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@teaching_unit_modules_router.post("/api/teaching/units/{unit_id}/phases/{phase_id}/modules/reorder")
async def reorder_unit_phase_modules(request: Request, unit_id: str, phase_id: str, payload: UnitModuleReorderPayload):
    """Reorder (and move) modules for a phase (author only)."""

    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(phase_id):
        return _private_error({"error": "bad_request", "detail": "invalid_phase_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(repo, "reorder_unit_phase_modules_owned")
    if repo_error:
        return repo_error

    ids, ids_error = _validate_uuid_id_list(
        payload.module_ids,
        array_detail="module_ids_must_be_array",
        empty_detail="empty_module_ids",
        duplicate_detail="duplicate_module_ids",
        invalid_detail="invalid_module_ids",
    )
    if ids_error:
        return ids_error

    try:
        ordered = repo.reorder_unit_phase_modules_owned(unit_id=unit_id, phase_id=phase_id, author_id=sub, module_ids=ids)
    except ValueError as exc:
        detail = str(exc) or "bad_request"
        if detail == "invalid_unit_type":
            return _private_error({"error": "bad_request", "detail": "invalid_unit_type"}, status_code=400)
        return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
    except LookupError as exc:
        detail = str(exc) or ""
        if detail in {"module_not_in_unit", "phase_not_found"}:
            return _private_error({"error": "not_found"}, status_code=404)
        return _private_error({"error": "bad_request", "detail": "invalid_module_ids"}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    except TeachingRepositoryUnavailable:
        raise
    except Exception as exc:
        sqlstate = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
        if sqlstate == "23514":
            return _private_error(
                {"error": "bad_request", "detail": "edge_constraint_violation"},
                status_code=400,
            )
        raise

    return _json_private([_serialize_unit_module(m) for m in ordered], status_code=200, vary_origin=True)
