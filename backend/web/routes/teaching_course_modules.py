"""Teaching course-module routes.

Why:
    Course-module authoring controls the relationship between a Course and its
    Units. The HTTP adapter belongs in this focused router, while repository
    access and guards remain shared providers during the refactor.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from backend.teaching.errors import TeachingRepositoryUnavailable
from backend.web.routes import teaching_guards
from backend.web.routes.teaching import _get_repo
from backend.web.routes.teaching_payloads import (
    CourseModuleCreatePayload,
    CourseModuleReorderPayload,
    ModuleSectionVisibilityPayload,
)
from backend.web.routes.teaching_serialization import _serialize_module, _serialize_section
from backend.web.routes.teaching_shared import (
    _current_sub,
    _is_uuid_like,
    _json_private,
    _private_error,
    _require_teacher,
    _role_in,
)


teaching_course_modules_router = APIRouter(tags=["Teaching"])
logger = logging.getLogger("gustav.web.teaching.course_modules")


@teaching_course_modules_router.get("/api/teaching/courses/{course_id}/modules")
async def list_course_modules(request: Request, course_id: str):
    """List modules for a course owned by the current teacher."""

    user, error = _require_teacher(request)
    if error:
        return error
    sub = _current_sub(user)
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        modules = _get_repo().list_course_modules_for_owner(course_id, sub)
    except TeachingRepositoryUnavailable:
        raise
    except Exception as exc:
        logger.warning("list_course_modules failed cid=%s err=%s", course_id[-6:], exc.__class__.__name__)
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return JSONResponse(content=[_serialize_module(module) for module in modules], status_code=200)


@teaching_course_modules_router.post("/api/teaching/courses/{course_id}/modules")
async def create_course_module(request: Request, course_id: str, payload: CourseModuleCreatePayload):
    """Attach a unit as a module within a course owned by the caller."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    sub = _current_sub(user)
    unit_id = payload.unit_id
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    try:
        guard_course = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
        if guard_course:
            return guard_course
        guard_unit = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
        if guard_unit:
            return guard_unit
        module = _get_repo().create_course_module_owned(
            course_id,
            sub,
            unit_id=unit_id,
            context_notes=payload.context_notes,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "duplicate_module":
            return JSONResponse({"error": "conflict"}, status_code=409)
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return _json_private(_serialize_module(module), status_code=201)


@teaching_course_modules_router.post("/api/teaching/courses/{course_id}/modules/reorder")
async def reorder_course_modules(request: Request, course_id: str, payload: CourseModuleReorderPayload):
    """Reorder modules within a course atomically."""

    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(course_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_course_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    module_ids = payload.module_ids
    if not isinstance(module_ids, list):
        return JSONResponse({"error": "bad_request", "detail": "invalid_module_ids"}, status_code=400)
    if len(module_ids) == 0:
        return JSONResponse({"error": "bad_request", "detail": "empty_reorder"}, status_code=400)
    if len(set(module_ids)) != len(module_ids):
        return JSONResponse({"error": "bad_request", "detail": "duplicate_module_ids"}, status_code=400)
    if any(not _is_uuid_like(module_id) for module_id in module_ids):
        return JSONResponse({"error": "bad_request", "detail": "invalid_module_ids"}, status_code=400)
    try:
        modules = repo.reorder_course_modules_owned(course_id, sub, module_ids)
    except ValueError as exc:
        return JSONResponse({"error": "bad_request", "detail": str(exc)}, status_code=400)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return JSONResponse(content=[_serialize_module(module) for module in modules], status_code=200)


@teaching_course_modules_router.delete("/api/teaching/courses/{course_id}/modules/{module_id}")
async def delete_course_module(request: Request, course_id: str, module_id: str):
    """Remove a unit from a course owned by the current teacher."""

    user, error = _require_teacher(request)
    if error:
        return error
    if not _is_uuid_like(course_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_course_id"}, status_code=400)
    if not _is_uuid_like(module_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_module_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        csrf = teaching_guards._csrf_guard(request)
        if csrf:
            return csrf
        deleted = _get_repo().delete_course_module_owned(course_id, module_id, sub)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if not deleted:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@teaching_course_modules_router.patch(
    "/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility"
)
async def update_module_section_visibility(
    request: Request,
    course_id: str,
    module_id: str,
    section_id: str,
    payload: ModuleSectionVisibilityPayload,
):
    """Toggle the visibility of a section within a course module."""

    user, error = _require_teacher(request)
    if error:
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(course_id):
        return _private_error({"error": "bad_request", "detail": "invalid_course_id"}, status_code=400, vary_origin=True)
    if not _is_uuid_like(module_id):
        return _private_error({"error": "bad_request", "detail": "invalid_module_id"}, status_code=400, vary_origin=True)
    if not _is_uuid_like(section_id):
        return _private_error({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400, vary_origin=True)
    sub = _current_sub(user)
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        if isinstance(guard, JSONResponse):
            guard.headers.setdefault("Cache-Control", "private, no-store")
            guard.headers.setdefault("Vary", "Origin")
            return guard
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)
    visible_value = payload.visible
    if visible_value is None:
        return _private_error({"error": "bad_request", "detail": "missing_visible"}, status_code=400, vary_origin=True)
    if not isinstance(visible_value, bool):
        return _private_error(
            {"error": "bad_request", "detail": "invalid_visible_type"},
            status_code=400,
            vary_origin=True,
        )
    try:
        record = _get_repo().set_module_section_visibility(course_id, module_id, section_id, sub, visible_value)
    except LookupError as exc:
        detail = str(exc) or "not_found"
        return _private_error({"error": "not_found", "detail": detail}, status_code=404, vary_origin=True)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)
    return _json_private(record, status_code=200, vary_origin=True)


@teaching_course_modules_router.get("/api/teaching/courses/{course_id}/modules/{module_id}/sections/releases")
async def list_module_section_releases(request: Request, course_id: str, module_id: str):
    """List release state entries for sections in a course module."""

    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)
    if not _is_uuid_like(course_id):
        return _private_error({"error": "bad_request", "detail": "invalid_course_id"}, status_code=400, vary_origin=True)
    if not _is_uuid_like(module_id):
        return _private_error({"error": "bad_request", "detail": "invalid_module_id"}, status_code=400, vary_origin=True)
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        if isinstance(guard, JSONResponse):
            guard.headers.setdefault("Cache-Control", "private, no-store")
            guard.headers.setdefault("Vary", "Origin")
            return guard
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        repo = _get_repo()
        if isinstance(repo, DBTeachingRepo):
            releases = repo.list_module_section_releases_owned(course_id, module_id, sub)
        else:
            module = repo.course_modules.get(module_id)
            if not module or module.course_id != course_id:
                return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)
            releases = [rec for (mid, _sid), rec in repo.module_section_releases.items() if mid == module_id]
    except LookupError:
        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)
    return _json_private(releases, status_code=200, vary_origin=True)


@teaching_course_modules_router.get("/api/teaching/courses/{course_id}/modules/{module_id}/sections")
async def list_module_sections_with_visibility(request: Request, course_id: str, module_id: str):
    """List module sections with section-level visibility state."""

    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        error.headers.setdefault("Cache-Control", "private, no-store")
        error.headers.setdefault("Vary", "Origin")
        return error
    if not _is_uuid_like(course_id):
        return _private_error({"error": "bad_request", "detail": "invalid_course_id"}, status_code=400, vary_origin=True)
    if not _is_uuid_like(module_id):
        return _private_error({"error": "bad_request", "detail": "invalid_module_id"}, status_code=400, vary_origin=True)
    sub = _current_sub(user)
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        if isinstance(guard, JSONResponse):
            guard.headers.setdefault("Cache-Control", "private, no-store")
            guard.headers.setdefault("Vary", "Origin")
            return guard
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)

    unit_id: str | None = None
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        modules = repo.list_course_modules_for_owner(course_id, sub)
        module_rows = modules if isinstance(repo, DBTeachingRepo) else [asdict(m) if is_dataclass(m) else m for m in modules]
        for module in module_rows:
            if str(module.get("id")) == str(module_id):
                unit_id = str(module.get("unit_id") or "")
                break
    except TeachingRepositoryUnavailable:
        raise
    except Exception:
        unit_id = None
    if not unit_id:
        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        repo = _get_repo()
        if isinstance(repo, DBTeachingRepo):
            sections = repo.list_sections_for_author(unit_id, sub)
            releases = repo.list_module_section_releases_owned(course_id, module_id, sub)
        else:
            sections = [_serialize_section(section) for section in repo.list_sections_for_author(unit_id, sub)]
            releases = repo.list_module_section_releases_owned(course_id, module_id, sub)
    except LookupError:
        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)
    except TeachingRepositoryUnavailable:
        raise
    except Exception:
        sections, releases = [], []

    release_by_section: dict[str, dict] = {str(row.get("section_id")): row for row in releases}
    out: list[dict] = []
    for section in sections:
        section_id = str(section.get("id"))
        release = release_by_section.get(section_id)
        visible = bool(release.get("visible")) if isinstance(release, dict) else False
        released_at = release.get("released_at") if isinstance(release, dict) and visible else None
        out.append(
            {
                "id": section_id,
                "unit_id": str(section.get("unit_id") or ""),
                "title": str(section.get("title") or ""),
                "position": max(1, int(section.get("position") or 1)),
                "visible": visible,
                "released_at": released_at,
            }
        )
    return _json_private(out, status_code=200, vary_origin=True)
