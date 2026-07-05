"""
Teaching (Unterrichten) API routes for course management.

Why:
    Provide minimal endpoints to create and list courses contract-first. The
    adapter enforces authentication (middleware) and authorization (role checks)
    and delegates persistence to an injected repository.

Notes:
    - Clean Architecture: Keep business rules simple and independent of FastAPI.
    - Security: Only teachers may create/update/delete courses. Students can list
      courses they belong to (not covered in the initial test slice).
    - Persistence: Prefers the Postgres-backed repo when psycopg and DSN are
      available; falls back to an in-memory repo for tests/local offline work.
      Tests can call `set_repo` to override the implementation for isolation.
"""

from __future__ import annotations

import logging

import time
from dataclasses import asdict, is_dataclass
import os
import sys as _sys
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
import asyncio

from fastapi import APIRouter, Request
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse, Response

from backend.teaching.services.materials import MaterialFileSettings, MaterialsService
from backend.teaching.services.live_student_overview import MAX_UNIT_IDS, StudentLiveOverviewService
from backend.teaching.repo_row_mappers import compute_average_score_from_analysis  # noqa: F401
from backend.teaching.storage import NullStorageAdapter, StorageAdapterProtocol
from backend.storage.config import get_submissions_bucket
from backend.web.routes.teaching_shared import (
    _current_sub,
    _is_uuid_like,
    _json_private,
    _private_error,
    _require_teacher,
)
from backend.web.routes.teaching_serialization import (
    _build_latest_submission_payload,
    _build_live_delta_cells,
    _build_live_summary_rows,
)
from backend.web.routes.teaching_task_services import (
    configure_task_service_repo_provider,
)
from backend.web.routes import teaching_guards
from backend.web.routes.teaching_authoring import (
    _is_signature_compat_type_error,
    configure_teaching_authoring_repo_provider,
)
from backend.web.routes.teaching_guards import (
    configure_teaching_guard_repo_provider,
)
from backend.web.routes.teaching_validation import (
    canonical_uuid as _canonical_uuid,
    safe_int as _safe_int,
)
from backend.web.routes import teaching_course_state, teaching_payloads, teaching_serialization, teaching_storage_cleanup
from backend.web.routes.teaching_storage_cleanup import (
    metadata_page_keys as _metadata_page_keys,  # noqa: F401 - kept for route module compatibility
    unit_delete_storage_metadata_dsn as _unit_delete_storage_metadata_dsn,  # noqa: F401
)
from backend.web.routes.teaching_submission_files import (
    download_bytes_with_limit as _download_bytes_with_limit,
    safe_download_filename as _safe_download_filename,
    teaching_submission_file_href as _teaching_submission_file_href,
)
from backend.web.routes import teaching_inmemory_repo

teaching_router = APIRouter(tags=["Teaching"])  # explicit paths below
logger = logging.getLogger("gustav.web.teaching")


def _collect_unit_delete_storage_objects(repo: object, *, unit_id: str) -> list[tuple[str, str]]:
    """Collect object storage entries that must be removed before deleting a unit."""

    return teaching_storage_cleanup.collect_unit_delete_storage_objects(
        repo,
        unit_id=unit_id,
        materials_bucket=MATERIAL_FILE_SETTINGS.storage_bucket,
    )


def _delete_unit_storage_objects(objects: list[tuple[str, str]]) -> None:
    """Delete collected storage objects using the active Teaching storage adapter."""

    teaching_storage_cleanup.delete_storage_objects(STORAGE_ADAPTER, objects)


# Optional storage wiring helper (lazy rewire for local Supabase E2E)
try:  # pragma: no cover - simple import guard
    from backend.web.storage_wiring import wire_supabase_adapter_if_configured as _wire_storage  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    _wire_storage = None  # type: ignore


# --- In-memory persistence (MVP fallback) ---------------------------------------

_UNSET = teaching_inmemory_repo._UNSET
_is_unset = teaching_inmemory_repo._is_unset
Course = teaching_inmemory_repo.Course
Unit = teaching_inmemory_repo.Unit
SectionData = teaching_inmemory_repo.SectionData
CourseModuleData = teaching_inmemory_repo.CourseModuleData
MaterialData = teaching_inmemory_repo.MaterialData
TaskData = teaching_inmemory_repo.TaskData
ConcernBoxEntryData = teaching_inmemory_repo.ConcernBoxEntryData
InMemoryTeachingRepo = teaching_inmemory_repo.InMemoryTeachingRepo

# Backwards-compatible test/import alias. New code should import
# InMemoryTeachingRepo from teaching_inmemory_repo directly.
_Repo = InMemoryTeachingRepo

UnitCreatePayload = teaching_payloads.UnitCreatePayload
UnitUpdatePayload = teaching_payloads.UnitUpdatePayload
TaskCreatePayload = teaching_payloads.TaskCreatePayload
TaskUpdatePayload = teaching_payloads.TaskUpdatePayload
TaskReorderPayload = teaching_payloads.TaskReorderPayload
MaterialCreatePayload = teaching_payloads.MaterialCreatePayload
MaterialFinalizePayload = teaching_payloads.MaterialFinalizePayload
MaterialReorderPayload = teaching_payloads.MaterialReorderPayload
MaterialUpdatePayload = teaching_payloads.MaterialUpdatePayload
MaterialUploadIntentPayload = teaching_payloads.MaterialUploadIntentPayload
UnitModuleCreatePayload = teaching_payloads.UnitModuleCreatePayload
UnitModuleEdgePayload = teaching_payloads.UnitModuleEdgePayload
UnitModuleReorderPayload = teaching_payloads.UnitModuleReorderPayload
UnitModuleUpdatePayload = teaching_payloads.UnitModuleUpdatePayload
UnitPhaseCreatePayload = teaching_payloads.UnitPhaseCreatePayload
UnitPhaseReorderPayload = teaching_payloads.UnitPhaseReorderPayload
UnitPhaseUpdatePayload = teaching_payloads.UnitPhaseUpdatePayload
_serialize_unit = teaching_serialization._serialize_unit
_serialize_task = teaching_serialization._serialize_task
_serialize_material = teaching_serialization._serialize_material
_serialize_unit_graph_edge = teaching_serialization._serialize_unit_graph_edge
_serialize_unit_module = teaching_serialization._serialize_unit_module
_serialize_unit_phase_public = teaching_serialization._serialize_unit_phase_public


# Try to use DB-backed repo when available; fallback to in-memory for dev/tests
try:  # late import to avoid hard dependency during unit tests
    from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
except Exception as exc:  # pragma: no cover - import failures in dev/test envs
    DBTeachingRepo = None  # type: ignore
    _DB_REPO_IMPORT_ERROR = exc
else:
    _DB_REPO_IMPORT_ERROR = None


def _build_default_repo():
    """Prefer DB-backed TeachingRepo; fall back to in-memory if unavailable.

    Matches the original project behavior so DB-based contract tests run when
    a fake psycopg/test DSN is provided; otherwise we degrade gracefully.
    """
    if DBTeachingRepo is None:
        if _DB_REPO_IMPORT_ERROR:
            logger.warning("Teaching repo import failed: %s", _DB_REPO_IMPORT_ERROR)
        return _Repo()
    try:
        return DBTeachingRepo()
    except Exception as exc:  # pragma: no cover - exercised when DSN missing
        logger.warning("Teaching repo unavailable (%s); using in-memory fallback", exc)
        return _Repo()


"""Lazy repo accessor to avoid import-time DB checks in tests."""
_REPO = None


def _current_teaching_module() -> object | None:
    """Return the currently active Teaching module instance when available."""
    return _sys.modules.get("backend.web.routes.teaching")

def _get_repo():  # pragma: no cover - simple accessor
    global _REPO, REPO
    module = _current_teaching_module()
    current_repo = getattr(module, "_REPO", None) if module is not None else _REPO
    if current_repo is None:
        current_repo = _build_default_repo()
        if module is not None:
            setattr(module, "_REPO", current_repo)
            setattr(module, "REPO", current_repo)
    # Keep the public module-level alias in sync for tests that do
    # `isinstance(routes_module.REPO, ...)`.
    _REPO = current_repo
    REPO = current_repo
    return current_repo


def _get_current_teaching_repo_for_provider() -> Any:
    """Resolve the active Teaching repository after legacy route-module reloads."""

    module = _current_teaching_module()
    getter = getattr(module, "_get_repo", None) if module is not None else None
    if callable(getter):
        return getter()
    return _get_repo()


configure_task_service_repo_provider(_get_current_teaching_repo_for_provider)
configure_teaching_guard_repo_provider(_get_current_teaching_repo_for_provider)
configure_teaching_authoring_repo_provider(_get_current_teaching_repo_for_provider)


# Back-compat symbol used in tests: set_repo() and _get_repo() keep this public
# alias in sync after the first real repository access. Keeping it empty at
# import time avoids DB connection attempts during route inventory and imports.
REPO = None

# Allow overriding the storage bucket via environment for deployments
_bucket = os.getenv("SUPABASE_STORAGE_BUCKET") or MaterialFileSettings().storage_bucket
MATERIAL_FILE_SETTINGS = MaterialFileSettings(storage_bucket=_bucket)
STORAGE_ADAPTER: StorageAdapterProtocol = NullStorageAdapter()
_STORAGE_ADAPTER_OVERRIDE_ACTIVE = False


def _sync_teaching_route_globals(*, adapter: StorageAdapterProtocol, override_active: bool) -> None:
    """Retarget already-registered Teaching route globals to the current adapter.

    Why:
        Some tests reload `backend.web.routes.teaching` while keeping the original FastAPI
        app instance alive. Route callables still reference the globals of the
        module instance they were created from. Without this sync, changing the
        adapter on a freshly imported module leaves old endpoints bound to a
        stale adapter and makes the suite order-dependent.
    """

    apps = []
    for module_name in ("backend.web.main",):
        main_module = _sys.modules.get(module_name)
        app = getattr(main_module, "app", None) if main_module is not None else None
        if app is not None:
            apps.append(app)
    try:
        from backend.web.app_composition import iter_registered_apps

        apps.extend(iter_registered_apps())
    except Exception:
        pass
    seen_apps: set[int] = set()
    for app in apps:
        app_id = id(app)
        if app_id in seen_apps:
            continue
        seen_apps.add(app_id)
        routes = getattr(app, "routes", None)
        if not routes:
            continue
        for route in routes:
            if not isinstance(route, APIRoute):
                continue
            if not str(getattr(route, "path", "")).startswith("/api/teaching"):
                continue
            route_globals = getattr(route.endpoint, "__globals__", None)
            if isinstance(route_globals, dict) and "STORAGE_ADAPTER" in route_globals:
                route_globals["STORAGE_ADAPTER"] = adapter
                route_globals["_STORAGE_ADAPTER_OVERRIDE_ACTIVE"] = override_active
                bound_teaching = route_globals.get("teaching_routes")
                if bound_teaching is not None:
                    setattr(bound_teaching, "STORAGE_ADAPTER", adapter)
                    setattr(bound_teaching, "_STORAGE_ADAPTER_OVERRIDE_ACTIVE", override_active)


def _sync_teaching_route_repo(repo: Any) -> None:
    """Retarget already-registered Teaching route globals to the current repo."""

    apps = []
    for module_name in ("backend.web.main",):
        main_module = _sys.modules.get(module_name)
        app = getattr(main_module, "app", None) if main_module is not None else None
        if app is not None:
            apps.append(app)
    try:
        from backend.web.app_composition import iter_registered_apps

        apps.extend(iter_registered_apps())
    except Exception:
        pass
    seen_apps: set[int] = set()
    for app in apps:
        app_id = id(app)
        if app_id in seen_apps:
            continue
        seen_apps.add(app_id)
        routes = getattr(app, "routes", None)
        if not routes:
            continue
        for route in routes:
            if not isinstance(route, APIRoute):
                continue
            if not str(getattr(route, "path", "")).startswith("/api/teaching"):
                continue
            route_globals = getattr(route.endpoint, "__globals__", None)
            if isinstance(route_globals, dict) and "_REPO" in route_globals:
                route_globals["_REPO"] = repo
                route_globals["REPO"] = repo
                bound_teaching = route_globals.get("teaching_routes")
                if bound_teaching is not None:
                    setattr(bound_teaching, "_REPO", repo)
                    setattr(bound_teaching, "REPO", repo)

def _get_materials_service() -> MaterialsService:
    return MaterialsService(_get_repo(), settings=MATERIAL_FILE_SETTINGS)

def _get_student_live_overview_service() -> StudentLiveOverviewService:
    return StudentLiveOverviewService(_get_repo())


def _current_download_bytes_with_limit() -> Any:
    """Resolve the active download helper after reloads or monkeypatching."""

    module = _current_teaching_module()
    downloader = getattr(module, "_download_bytes_with_limit", None) if module is not None else None
    return downloader or _download_bytes_with_limit


def set_repo(repo) -> None:
    """Allow tests to swap the teaching repository implementation."""
    global _REPO, REPO
    _REPO = repo
    REPO = repo
    for module_name in ("backend.web.routes.teaching",):
        module = _sys.modules.get(module_name)
        if module is None:
            continue
        setattr(module, "_REPO", repo)
        setattr(module, "REPO", repo)
    _sync_teaching_route_repo(repo)


def set_storage_adapter(adapter: StorageAdapterProtocol, *, override: bool = True) -> None:
    """Allow tests to provide a storage adapter (e.g., fake or stub)."""
    global STORAGE_ADAPTER, _STORAGE_ADAPTER_OVERRIDE_ACTIVE
    STORAGE_ADAPTER = adapter
    _STORAGE_ADAPTER_OVERRIDE_ACTIVE = bool(override)
    for module_name in ("backend.web.routes.teaching",):
        module = _sys.modules.get(module_name)
        if module is None:
            continue
        setattr(module, "STORAGE_ADAPTER", adapter)
        setattr(module, "_STORAGE_ADAPTER_OVERRIDE_ACTIVE", bool(override))
    _sync_teaching_route_globals(adapter=adapter, override_active=_STORAGE_ADAPTER_OVERRIDE_ACTIVE)


# --- Request/Response models -----------------------------------------------------

def _validate_uuid_id_list(
    raw_ids: object,
    *,
    array_detail: str,
    empty_detail: str,
    duplicate_detail: str,
    invalid_detail: str,
) -> tuple[list[str] | None, JSONResponse | None]:
    """Validate reorder payload id arrays without raising on unhashable items."""
    if not isinstance(raw_ids, list):
        return None, _private_error({"error": "bad_request", "detail": array_detail}, status_code=400)
    if len(raw_ids) == 0:
        return None, _private_error({"error": "bad_request", "detail": empty_detail}, status_code=400)

    ids: list[str] = []
    for item in raw_ids:
        if not isinstance(item, str):
            return None, _private_error({"error": "bad_request", "detail": invalid_detail}, status_code=400)
        norm = item.strip()
        if not norm or not _is_uuid_like(norm):
            return None, _private_error({"error": "bad_request", "detail": invalid_detail}, status_code=400)
        ids.append(_canonical_uuid(norm))

    if len(ids) != len(set(ids)):
        return None, _private_error({"error": "bad_request", "detail": duplicate_detail}, status_code=400)
    return ids, None


def _require_modular_repo_methods(repo: object, *method_names: str) -> JSONResponse | None:
    """Ensure modular endpoints run only when the repo implements required methods."""
    for method_name in method_names:
        if not callable(getattr(repo, method_name, None)):
            return _private_error({"error": "service_unavailable"}, status_code=503)
    return None


_MODULAR_UNIT_CREATE_REQUIRED_METHODS: tuple[str, ...] = (
    "list_unit_phases_for_author",
    "create_unit_phase",
    "update_unit_phase_title",
    "delete_unit_phase_for_author",
    "reorder_unit_phases_owned",
    "list_unit_modules_for_author",
    "create_unit_module_for_author",
    "update_unit_module_owned",
    "delete_unit_module_for_author",
    "list_unit_module_edges_for_author",
    "create_unit_module_edge_for_author",
    "delete_unit_module_edge_for_author",
    "reorder_unit_phase_modules_owned",
)


def _list_unit_modules_for_author_compat(repo: object, *, unit_id: str, author_id: str):
    """Call module listing with keyword args and controlled signature fallback."""
    try:
        return repo.list_unit_modules_for_author(unit_id=unit_id, author_id=author_id)  # type: ignore[attr-defined]
    except TypeError as exc:
        if not _is_signature_compat_type_error(exc):
            raise
        return repo.list_unit_modules_for_author(unit_id, author_id)  # type: ignore[attr-defined]


def _load_average_scores_by_submission_id(
    repo,
    owner_sub: str,
    submission_ids_by_student: dict[str, list[str]],
) -> dict[str, float | None]:
    """Load average scores for submissions where analysis is completed.

    Why:
        The teacher live matrix must only display an average score once the
        asynchronous analysis pipeline finished. Submissions that exist but are
        still pending must expose `average_score=None` (not 0.0).

    Security:
        Reads happen under RLS by impersonating each student via
        `app.current_sub`.
    """
    if not submission_ids_by_student:
        return {}
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            return repo.list_unit_live_average_scores_by_submission_id(
                owner_sub=owner_sub,
                submission_ids_by_student=submission_ids_by_student,
            )
    except Exception as exc:
        logger.warning("Unit live average score lookup failed — %s", exc)
    return {}


def _load_latest_submission_state_by_task(
    repo,
    owner_sub: str,
    course_id: str,
    task_ids_by_student: dict[str, list[str]],
) -> dict[tuple[str, str], dict[str, Any]]:
    """Load the latest submission state per `(student_sub, task_id)` under RLS."""
    if not task_ids_by_student:
        return {}
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            return repo.list_unit_live_submission_state_by_task(
                owner_sub=owner_sub,
                course_id=course_id,
                task_ids_by_student=task_ids_by_student,
            )
    except Exception as exc:
        logger.warning("Unit live latest submission lookup failed — %s", exc)
    return {}


def _load_unit_live_helper_rows(
    repo,
    *,
    owner_sub: str,
    course_id: str,
    unit_id: str,
    updated_since_dt: datetime | None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    """Load live helper rows compatibly across the old and new DB helper shapes.

    Why:
        The live matrix and delta endpoints recently started reading
        `score_raw/score_max` from `get_unit_latest_submissions_for_owner(...)`.
        Snapshot imports or partially migrated environments can still expose the
        older helper shape without these columns. We probe the new shape first
        and roll back to a savepoint before retrying the legacy projection.

    Returns:
        A normalized list of rows with stable keys:
        `student_sub`, `task_id`, `submission_id`, `score_raw`, `score_max`,
        `created_at_iso`, `completed_at_iso`, `h5p_completed`.
    """
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            return repo.list_unit_live_helper_rows(
                owner_sub=owner_sub,
                course_id=course_id,
                unit_id=unit_id,
                updated_since_dt=updated_since_dt,
                limit=int(limit),
                offset=int(offset),
            )
    except Exception as exc:
        logger.warning("Unit live helper row lookup failed — %s", exc)
    return []


# --- User directory adapter (mockable) ------------------------------------------

def resolve_student_names(subs: list[str]) -> dict[str, str]:
    """Resolve user IDs to display names via Keycloak directory (humanized).

    - Always attempt the directory call; on failure, fall back to "Unbekannt".
    - Humanize returned identifiers (emails/usernames) to "Vorname Nachname".
    - Never expose SUBs in the names returned by this function.
    """
    out: dict[str, str] = {}
    try:
        from backend.identity_access import directory  # type: ignore
        raw = directory.resolve_student_names(subs)
        for sid in subs:
            val = str((raw or {}).get(sid, "")).strip()
            if not val or val == sid:
                # Directory could not resolve the SUB. As a pragmatic fallback
                # for legacy imports, derive a display name from the identifier
                # itself when it clearly encodes an email (or legacy-email:...).
                # This prevents leaking raw emails: the humanizer strips the
                # domain and known prefixes.
                fallback = ""
                try:
                    if sid.startswith("legacy-email:") or ("@" in sid):
                        fallback = directory.humanize_identifier(sid)  # type: ignore[attr-defined]
                except Exception:
                    fallback = ""
                out[sid] = fallback or "Unbekannt"
            else:
                # Humanize emails/legacy/username patterns
                nice = directory.humanize_identifier(val)  # type: ignore[attr-defined]
                out[sid] = nice or "Unbekannt"
        return out
    except Exception:
        return {s: "Unbekannt" for s in subs}


def resolve_live_student_names_by_sub(subs: list[str]) -> dict[str, str]:
    """Resolve `/live` learner labels with person-name priority.

    Why:
        The live room should prefer a learner's first/last name, but still fall
        back to a stable login-style localpart when profile data is incomplete.
        The hot path must avoid fetching a fresh admin token for every single
        learner lookup.
    """
    try:
        from backend.identity_access import directory  # type: ignore
        return directory.resolve_live_student_names_by_sub(subs)  # type: ignore[attr-defined]
    except Exception:
        return _resolve_student_login_labels_runtime(subs)


def _summary_snapshot_cursor(repo: Any, owner_sub: str | None = None) -> str | None:
    """Return a DB-based live summary cursor when the teaching repo has a DSN.

    Why:
        The live dashboard seeds its next delta poll from the summary response.
        Using the database clock avoids host/DB skew that could otherwise hide a
        submission created right after the summary call. If the DB seed cannot be
        read, the caller must fail closed instead of silently inventing a host
        clock fallback.
    """
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if not isinstance(repo, DBTeachingRepo):
            return None
        if owner_sub is None:
            owner_sub = ""
        return repo.get_statement_timestamp(owner_sub=owner_sub)
    except Exception:
        return None
    return None


_DEFAULT_SUMMARY_SNAPSHOT_CURSOR = _summary_snapshot_cursor


def _resolve_student_names_runtime(subs: list[str]) -> dict[str, str]:
    """Resolve student names via the currently active Teaching module."""

    return resolve_student_names(subs)


def _resolve_student_login_labels_runtime(subs: list[str]) -> dict[str, str]:
    """Resolve login labels via the currently active Teaching module."""

    return resolve_student_login_labels_by_sub(subs)


def _summary_snapshot_cursor_runtime(repo: Any, owner_sub: str) -> str | None:
    """Resolve the active live summary cursor helper from the current module."""

    default = globals().get("_DEFAULT_SUMMARY_SNAPSHOT_CURSOR")
    local = _summary_snapshot_cursor
    if default is not None and callable(local) and local is not default:
        resolver = local
    else:
        module = _current_teaching_module()
        current = getattr(module, "_summary_snapshot_cursor", None) if module is not None else None
        resolver = current if default is not None and callable(current) and current is not default else local
    try:
        return resolver(repo, owner_sub)
    except TypeError:
        return resolver(repo)


def _current_max_unit_ids() -> int:
    """Return the active live-overview unit-id limit."""

    try:
        return max(1, int(MAX_UNIT_IDS))
    except Exception:
        return MAX_UNIT_IDS


def resolve_student_login_labels_by_sub(subs: list[str]) -> dict[str, str]:
    """Resolve user ids to login-style labels via direct directory lookups.

    Why:
        Live teacher views should show stable login identifiers, but must avoid
        the O(directory) role-member scan that the members page uses.
    """
    unique_subs = list(dict.fromkeys(str(sid or "").strip() for sid in subs if str(sid or "").strip()))
    if not unique_subs:
        return {}
    out: dict[str, str] = {}

    def _normalize_login_label(raw: str) -> str:
        value = str(raw or "").strip()
        if not value:
            return ""
        if value.startswith("legacy-email:"):
            value = value.split(":", 1)[1].strip()
        if "@" in value:
            value = value.split("@", 1)[0].strip()
        return value

    try:
        from backend.identity_access import directory  # type: ignore

        raw = directory.resolve_student_login_labels_by_sub(unique_subs)  # type: ignore[attr-defined]
        for sid in unique_subs:
            label = _normalize_login_label((raw or {}).get(sid, ""))
            if label and label.lower() != "unbekannt":
                out[sid] = label
                continue
            fallback = ""
            try:
                fallback = directory.localpart_identifier(sid)  # type: ignore[attr-defined]
            except Exception:
                fallback = ""
            out[sid] = fallback or "Unbekannt"
        return out
    except Exception:
        try:
            from backend.identity_access import directory  # type: ignore

            return {
                sid: (directory.localpart_identifier(sid) or "Unbekannt")  # type: ignore[attr-defined]
                for sid in unique_subs
            }
        except Exception:
            return {sid: "Unbekannt" for sid in unique_subs}


# --- Routes ----------------------------------------------------------------------

# Course handlers live in backend.web.routes.teaching_courses.

# Unit handlers live in backend.web.routes.teaching_units.

_MOVED_UNIT_MODULE_HANDLER_NAMES = frozenset(
    {
        "list_unit_phases",
        "create_unit_phase",
        "update_unit_phase",
        "delete_unit_phase",
        "reorder_unit_phases",
        "get_unit_modules_graph",
        "get_unit_module_content_target",
        "create_unit_module",
        "create_unit_module_edge",
        "delete_unit_module_edge",
        "delete_unit_module_edge_by_path",
        "update_unit_module",
        "delete_unit_module",
        "reorder_unit_phase_modules",
    }
)
_MOVED_UNIT_MATERIAL_HANDLER_NAMES = frozenset(
    {
        "list_section_materials",
        "create_section_material",
        "update_section_material",
        "delete_section_material",
        "create_section_material_upload_intent",
        "finalize_section_material_upload",
        "create_module_material",
        "update_module_material",
        "delete_module_material",
        "reorder_module_materials",
        "create_module_material_upload_intent",
        "finalize_module_material_upload",
        "get_section_material_download_url",
        "reorder_section_materials",
    }
)


def __getattr__(name: str) -> Any:
    """Expose moved Unit module handlers lazily for older tests and imports."""

    if name in _MOVED_UNIT_MODULE_HANDLER_NAMES:
        from backend.web.routes import teaching_unit_modules

        return getattr(teaching_unit_modules, name)
    if name in _MOVED_UNIT_MATERIAL_HANDLER_NAMES:
        from backend.web.routes import teaching_unit_materials

        return getattr(teaching_unit_materials, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Section handlers live in backend.web.routes.teaching_unit_sections.

# Task handlers live in backend.web.routes.teaching_unit_tasks.

# Course-module handlers live in backend.web.routes.teaching_course_modules.


_teacher_id_of = teaching_course_state.teacher_id_of
_prune_recently_deleted = teaching_course_state.prune_recently_deleted
_mark_recently_deleted = teaching_course_state.mark_recently_deleted
_was_recently_deleted = teaching_course_state.was_recently_deleted


def _resp_non_owner_or_unknown(course_id: str, owner_sub: str):
    """Return 404 when course does not exist, else 403 (non-owner).

    Why:
        Centralizes 404 vs 403 semantics to avoid duplication and subtle
        inconsistencies across endpoints. Uses a short "recently deleted"
        window to make immediate follow-ups deterministic for owners.

    Behavior:
        - If the same owner recently deleted the course: 404.
        - If `repo.course_exists` deterministically returns False: 404.
        - Otherwise: 403 to avoid leaking information.
    """
    repo = _get_repo()
    # Owner just deleted? Prefer 404 for immediate follow-ups
    if _was_recently_deleted(owner_sub, course_id):
        return _private_error({"error": "not_found"}, status_code=404)
    try:
        ex = repo.course_exists(course_id)
    except Exception:
        ex = None
    if ex is False:
        # Deterministic contract: non-existent course -> 404
        return _private_error({"error": "not_found"}, status_code=404)
    return _private_error({"error": "forbidden"}, status_code=403)


# Course-member handlers live in backend.web.routes.teaching_course_members.

async def get_unit_live_summary(
    request: Request,
    course_id: str,
    unit_id: str,
    updated_since: str | None = None,
    limit: int = 100,
    offset: int = 0,
    include_students: bool = True,
):
    """
    Live overview for a unit (owner): tasks and student rows with minimal status.

    Why:
        Provide a compact matrix (students × unit tasks) indicating only whether
        a submission exists per cell. Teachers can then drill into details
        without loading content in the summary call.

    Security:
        - Requires `teacher` role and course ownership.
        - Unit must be attached to the course for the owner.
        - Responses use private, no-store caching and vary by Origin.

    Notes:
        - Tasks are fetched via the owner scope; a dedicated application use case
          will consolidate this logic in a later iteration.
        - Submission lookups prefer the SECURITY DEFINER helper. When the helper
          is missing or inaccessible (e.g. migration not applied) we log a
          warning and fall back to RLS-safe bulk queries.
        - `updated_since` is optional; invalid timestamps produce
          `400 invalid_timestamp` so clients adjust their cursors.
    """
    repo = _get_repo()
    user, forbidden = _require_teacher(request)
    if forbidden:
        forbidden.headers.setdefault("Cache-Control", "private, no-store")
        forbidden.headers.setdefault("Vary", "Origin")
        return forbidden
    if not (_is_uuid_like(course_id) and _is_uuid_like(unit_id)):
        return _private_error({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, vary_origin=True)
    sub = _current_sub(user)

    updated_since_dt: datetime | None = None
    if updated_since:
        try:
            normalized = updated_since.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            updated_since_dt = parsed.astimezone(timezone.utc)
        except ValueError:
            return _private_error({"error": "bad_request", "detail": "invalid_timestamp"}, status_code=400, vary_origin=True)

    # Ownership guard
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        if isinstance(guard, JSONResponse):
            guard.headers.setdefault("Cache-Control", "private, no-store")
            guard.headers.setdefault("Vary", "Origin")
            return guard
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)

    # Verify unit is attached to course for the owner
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        repo = _get_repo()
        if isinstance(repo, DBTeachingRepo):
            modules = repo.list_course_modules_for_owner(course_id, sub)
        else:
            modules = [asdict(m) if is_dataclass(m) else m for m in repo.list_course_modules_for_owner(course_id, sub)]
    except Exception:
        modules = []
    if str(unit_id) not in {str(m.get("unit_id")) for m in modules}:
        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)
    snapshot_cursor = _summary_snapshot_cursor_runtime(repo, sub)
    if not snapshot_cursor:
        return _private_error(
            {"error": "service_unavailable", "detail": "summary_cursor_unavailable"},
            status_code=503,
            vary_origin=True,
        )

    # Build task list across the unit in position order
    tasks: list[dict] = []
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            sections = repo.list_sections_for_author(unit_id, sub)  # owner==author in tests
            for sec in sections:
                sec_tasks = repo.list_tasks_for_section_owned(unit_id, sec["id"], sub)
                for t in sec_tasks:
                    tasks.append({
                        "id": t["id"],
                        # API contract: tasks carry instruction_md (not a separate title)
                        "instruction_md": t.get("instruction_md") or "",
                        "position": int(t.get("position") or 0),
                        "kind": str(t.get("kind") or "native"),
                    })
        else:
            # In-memory repo fallback
            section_ids = [sid for sid, sd in repo.sections.items() if sd.unit_id == unit_id]
            section_ids.sort(key=lambda sid: repo.sections[sid].position)
            for sid in section_ids:
                tids = repo.task_ids_by_section.get(sid, [])
                for tid in tids:
                    td = repo.tasks[tid]
                    tasks.append({
                        "id": td.id,
                        "instruction_md": td.instruction_md or "",
                        "position": int(td.position),
                        "kind": str(getattr(td, "kind", "native") or "native"),
                    })
    except Exception:
        tasks = []

    rows_out: list[dict] = []
    if include_students:
        roster: list[tuple[str, str]] = []
        try:
            from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
            if isinstance(repo, DBTeachingRepo):
                roster = repo.list_members_for_owner(course_id, sub, limit=limit, offset=offset)
            else:
                members = repo.members.get(course_id, {})
                roster = sorted([(k, v) for k, v in members.items()], key=lambda kv: kv[1])
                roster = roster[offset: offset + limit]
        except Exception:
            roster = []
        member_subs = [sid for sid, _ in roster]
        names = await asyncio.to_thread(resolve_live_student_names_by_sub, member_subs)

        has_map: set[tuple[str, str]] = set()
        avg_map: dict[tuple[str, str], float | None] = {}
        h5p_map: dict[tuple[str, str], bool] = {}
        score_map: dict[tuple[str, str], tuple[int | None, int | None]] = {}
        created_at_map: dict[tuple[str, str], str | None] = {}
        try:
            from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
            if isinstance(repo, DBTeachingRepo):
                try:
                    aggregate_rows = repo.list_unit_latest_submission_aggregates_for_owner(
                        course_id=course_id,
                        unit_id=unit_id,
                        owner_sub=sub,
                        student_subs=member_subs,
                    )
                    has_map = {
                        (str(row.get("student_sub") or ""), str(row.get("task_id") or ""))
                        for row in aggregate_rows
                        if bool(row.get("has_submission"))
                    }
                    avg_map = {
                        (str(row.get("student_sub") or ""), str(row.get("task_id") or "")): row.get("average_score")
                        for row in aggregate_rows
                    }
                    h5p_map = {
                        (str(row.get("student_sub") or ""), str(row.get("task_id") or "")): bool(row.get("h5p_completed"))
                        for row in aggregate_rows
                        if row.get("h5p_completed") is not None
                    }
                    score_map = {
                        (str(row.get("student_sub") or ""), str(row.get("task_id") or "")): (
                            _safe_int(row.get("score_raw")),
                            _safe_int(row.get("score_max")),
                        )
                        for row in aggregate_rows
                    }
                    created_at_map = {
                        (str(row.get("student_sub") or ""), str(row.get("task_id") or "")): str(row.get("created_at_iso") or "")
                        for row in aggregate_rows
                        if row.get("created_at_iso")
                    }
                except Exception as exc:
                    logger.warning(
                        "Unit summary bulk aggregate fallback: get_unit_latest_submission_aggregates_for_owner unavailable — %s",
                        exc,
                        extra={"course_id": course_id, "unit_id": unit_id},
                    )
                    helper_rows: list[dict[str, Any]] = []
                    try:
                        helper_rows = _load_unit_live_helper_rows(
                            repo,
                            owner_sub=sub,
                            course_id=course_id,
                            unit_id=unit_id,
                            updated_since_dt=updated_since_dt,
                            limit=int(limit),
                            offset=int(offset),
                        )
                        has_map = {(str(row["student_sub"]), str(row["task_id"])) for row in helper_rows}
                        task_ids_by_student: dict[str, list[str]] = {}
                        for row in helper_rows:
                            student_sub = str(row["student_sub"])
                            task_ids_by_student.setdefault(student_sub, []).append(str(row["task_id"]))
                        latest_state_by_task = (
                            _load_latest_submission_state_by_task(repo, sub, course_id, task_ids_by_student)
                            if any(
                                row.get("score_raw") is None or row.get("score_max") is None
                                for row in helper_rows
                            )
                            else {}
                        )
                        submission_ids_by_student: dict[str, list[str]] = {}
                        for row in helper_rows:
                            student_sub = str(row["student_sub"])
                            task_id = str(row["task_id"])
                            latest_state = latest_state_by_task.get((student_sub, task_id), {})
                            submission_id = latest_state.get("submission_id") or row.get("submission_id")
                            if submission_id:
                                submission_ids_by_student.setdefault(student_sub, []).append(submission_id)
                            score_raw = _safe_int(row.get("score_raw"))
                            score_max = _safe_int(row.get("score_max"))
                            if score_raw is None or score_max is None:
                                score_raw = latest_state.get("score_raw", score_raw)
                                score_max = latest_state.get("score_max", score_max)
                            score_map[(student_sub, task_id)] = (score_raw, score_max)
                        avg_by_id = _load_average_scores_by_submission_id(repo, sub, submission_ids_by_student)
                        avg_map = {
                            (
                                str(row["student_sub"]),
                                str(row["task_id"]),
                            ): avg_by_id.get(
                                latest_state_by_task.get((str(row["student_sub"]), str(row["task_id"])), {}).get(
                                    "submission_id"
                                )
                                or row.get("submission_id")
                            )
                            for row in helper_rows
                        }
                        h5p_map = {
                            (str(row["student_sub"]), str(row["task_id"])): bool(row["h5p_completed"])
                            for row in helper_rows
                            if row.get("h5p_completed") is not None
                        }
                        created_at_map = {
                            (str(row["student_sub"]), str(row["task_id"])): str(row.get("created_at_iso") or "")
                            for row in helper_rows
                            if row.get("created_at_iso")
                        }

                        if tasks and member_subs:
                            task_ids = [t["id"] for t in tasks]
                            if not has_map:
                                fallback_rows = repo.list_unit_live_summary_fallback_rows(
                                    owner_sub=sub,
                                    course_id=course_id,
                                    task_ids=task_ids,
                                    member_subs=member_subs,
                                )
                                has_map = {(str(student_sub), str(task_id)) for student_sub, task_id, _ in fallback_rows}
                                created_at_map.update(
                                    {
                                        (str(student_sub), str(task_id)): str(created_at_iso or "")
                                        for student_sub, task_id, created_at_iso in fallback_rows
                                        if created_at_iso
                                    }
                                )
                            if not has_map:
                                for sid in member_subs:
                                    sid_rows = repo.list_unit_live_task_ids_for_student(
                                        owner_sub=sub,
                                        course_id=course_id,
                                        student_sub=sid,
                                        task_ids=task_ids,
                                    )
                                    for task_id, created_at_iso in sid_rows:
                                        has_map.add((sid, task_id))
                                        if created_at_iso:
                                            created_at_map[(sid, task_id)] = str(created_at_iso)
                    except Exception as legacy_exc:
                        logger.warning(
                            "Unit summary fallback: get_unit_latest_submissions_for_owner unavailable — %s",
                            legacy_exc,
                            extra={"course_id": course_id, "unit_id": unit_id},
                        )
                        helper_rows = []
        except Exception:
            has_map = set()
            avg_map = {}
            h5p_map = {}
            score_map = {}
            created_at_map = {}

        rows_out = _build_live_summary_rows(
            members=member_subs,
            names=names,
            tasks=tasks,
            has_map=has_map,
            avg_map=avg_map,
            created_at_map=created_at_map,
            score_map=score_map,
            h5p_map=h5p_map,
        )

    payload = {
        "cursor": snapshot_cursor,
        "tasks": tasks,
        "rows": rows_out,
    }
    # private + Vary: Origin per contract
    return _json_private(payload, status_code=200, vary_origin=True)


async def get_unit_live_delta(
    request: Request,
    course_id: str,
    unit_id: str,
    updated_since: str,
    limit: int = 200,
    offset: int = 0,
):
    """Return only changed submission cells since `updated_since` (owner-only).

    Intent (Why):
        Supports polling-based live updates for the teacher's unit view. Instead
        of streaming, the client periodically requests only changed cells since
        the last known cursor to keep payloads small and behaviour simple.

    Parameters:
        - course_id: UUID of the course (path). Must be owned by the caller.
        - unit_id: UUID of the unit (path). Must be attached to the course.
        - updated_since: ISO-8601 timestamp (with timezone). The endpoint returns
          only cells whose "change timestamp" is strictly greater than this value.
        - limit/offset: Pagination of changed cells (server clamps range).

    Expected behaviour:
        - 200 with {"cells": [...]} when there are changes. Each cell contains
          student_sub, task_id, has_submission (bool), changed_at (ISO, microseconds).
        - 204 No Content when there are no changes since the cursor.
        - 400 for invalid UUIDs or malformed timestamps.
        - 403 when the caller is not the course owner; 404 when the unit is not
          attached to the course.

    Security / Permissions:
        - Caller must be a teacher and owner of the course (RLS enforced via
          `gustav_limited` + app.current_sub, plus explicit ownership checks).
        - No content (student work) is returned, only minimal status/IDs.
        - Responses use "private, no-store" and vary by Origin to prevent leaks.
    """
    repo = _get_repo()
    user, forbidden = _require_teacher(request)
    if forbidden:
        forbidden.headers.setdefault("Cache-Control", "private, no-store")
        forbidden.headers.setdefault("Vary", "Origin")
        return forbidden
    if not (_is_uuid_like(course_id) and _is_uuid_like(unit_id)):
        return _private_error({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, vary_origin=True)

    limit = max(1, min(int(limit or 200), 500))
    offset = max(0, int(offset or 0))

    try:
        normalized = updated_since.replace("Z", "+00:00")
        updated_since_dt = datetime.fromisoformat(normalized)
        if updated_since_dt.tzinfo is None:
            updated_since_dt = updated_since_dt.replace(tzinfo=timezone.utc)
        updated_since_dt = updated_since_dt.astimezone(timezone.utc)
        original_updated_dt = updated_since_dt
        # Use the client's cursor as the DB lower bound (exclusive in SQL helper).
        # We rely on strict in-memory filtering to avoid duplicates.
        db_lower_bound = original_updated_dt
    except ValueError:
        return _private_error({"error": "bad_request", "detail": "invalid_timestamp"}, status_code=400, vary_origin=True)

    sub = _current_sub(user)
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        if isinstance(guard, JSONResponse):
            guard.headers.setdefault("Cache-Control", "private, no-store")
            guard.headers.setdefault("Vary", "Origin")
            return guard
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            modules = repo.list_course_modules_for_owner(course_id, sub)
        else:
            modules = [asdict(m) if is_dataclass(m) else m for m in repo.list_course_modules_for_owner(course_id, sub)]
    except Exception:
        modules = []
    if str(unit_id) not in {str(m.get("unit_id")) for m in modules}:
        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)

    cells: list[dict] = []
    debug = (os.getenv("DEBUG_DELTA", "").strip() == "1")
    EPS = timedelta(seconds=1)
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            helper_rows: list[dict[str, Any]] = []
            helper_ok = True
            avg_by_id: dict[str, float | None] = {}
            try:
                helper_rows = _load_unit_live_helper_rows(
                    repo,
                    owner_sub=sub,
                    course_id=course_id,
                    unit_id=unit_id,
                    updated_since_dt=db_lower_bound,
                    limit=int(limit),
                    offset=int(offset),
                )
                task_ids_by_student: dict[str, list[str]] = {}
                for row in helper_rows:
                    student_sub = str(row["student_sub"])
                    task_ids_by_student.setdefault(student_sub, []).append(str(row["task_id"]))
                latest_state_by_task = (
                    _load_latest_submission_state_by_task(repo, sub, course_id, task_ids_by_student)
                    if any(
                        row.get("score_raw") is None or row.get("score_max") is None
                        for row in helper_rows
                    )
                    else {}
                )
                latest_changed_by_pair = repo.list_unit_live_latest_changed_at_by_pairs(
                    owner_sub=sub,
                    course_id=course_id,
                    task_ids_by_student=task_ids_by_student,
                )
                submission_ids_by_student: dict[str, list[str]] = {}
                for row in helper_rows:
                    student_sub = str(row["student_sub"])
                    task_id = str(row["task_id"])
                    submission_id = (
                        latest_state_by_task.get((student_sub, task_id), {}).get("submission_id")
                        or row.get("submission_id")
                    )
                    if submission_id:
                        submission_ids_by_student.setdefault(student_sub, []).append(submission_id)
                avg_by_id = _load_average_scores_by_submission_id(repo, sub, submission_ids_by_student)
            except Exception as exc:
                logger.warning(
                    "Unit delta fallback: helper unavailable — %s",
                    exc,
                    extra={"course_id": course_id, "unit_id": unit_id},
                )
                helper_rows = []
                helper_ok = False

            if helper_ok:
                cells = _build_live_delta_cells(
                    helper_rows=helper_rows,
                    latest_state_by_task=latest_state_by_task,
                    avg_by_id=avg_by_id,
                    latest_changed_by_pair=latest_changed_by_pair,
                    original_updated_dt=original_updated_dt,
                    logger_obj=logger,
                    debug=logger.isEnabledFor(logging.DEBUG) or debug,
                    timestamp_provider=lambda: datetime.now(timezone.utc),
                    epsilon_seconds=1,
                )

            if not helper_ok:
                try:
                    fallback_rows = repo.list_unit_live_delta_fallback_rows(
                        owner_sub=sub,
                        course_id=course_id,
                        changed_since=db_lower_bound,
                        limit=int(limit),
                        offset=int(offset),
                    )
                except Exception:
                    fallback_rows = []
                for student_sub, task_id, changed_ts in fallback_rows:
                    try:
                        changed_dt = changed_ts.astimezone(timezone.utc)
                    except Exception:
                        changed_dt = datetime.now(timezone.utc)
                    include = changed_dt > (original_updated_dt - EPS)
                    if not include:
                        continue
                    emit_dt = (changed_dt + EPS) if changed_dt > original_updated_dt else (original_updated_dt + EPS)
                    changed_iso = emit_dt.isoformat(timespec="microseconds")
                    cells.append(
                        {
                            "student_sub": student_sub,
                            "task_id": task_id,
                            "has_submission": True,
                            "average_score": None,
                            "changed_at": changed_iso,
                        }
                    )

    except Exception as exc:
        logger.warning(
            "Unit delta query failed falling back to empty delta — %s",
            exc,
            extra={"course_id": course_id, "unit_id": unit_id},
        )

    if not cells:
        return Response(status_code=204, headers={"Cache-Control": "private, no-store", "Vary": "Origin"})

    payload = {"cells": cells}
    return _json_private(payload, status_code=200, vary_origin=True)


async def get_student_live_overview(request: Request, course_id: str, student_sub: str):
    """Return a teacher-facing live overview for one student across course units.

    Why:
        Teachers need the inverse perspective of the unit live matrix:
        `course x student x selected units`. The endpoint exposes only task-level
        status aggregates and keeps the richer submission detail on the existing
        latest-submission endpoint.
    """
    user, forbidden = _require_teacher(request)
    if forbidden:
        forbidden.headers.setdefault("Cache-Control", "private, no-store")
        forbidden.headers.setdefault("Vary", "Origin")
        return forbidden
    if not _is_uuid_like(course_id):
        return _private_error({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, vary_origin=True)

    raw_unit_ids = request.query_params.getlist("unit_ids") if "unit_ids" in request.query_params else None
    normalized_unit_ids: list[str] | None = None
    if raw_unit_ids is not None:
        normalized_unit_ids = []
        seen: set[str] = set()
        for raw in raw_unit_ids:
            trimmed = str(raw or "").strip()
            if not trimmed:
                continue
            if not _is_uuid_like(trimmed):
                return _private_error({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, vary_origin=True)
            canonical = _canonical_uuid(trimmed)
            if canonical in seen:
                continue
            seen.add(canonical)
            normalized_unit_ids.append(canonical)
        if len(normalized_unit_ids) > _current_max_unit_ids():
            return _private_error({"error": "bad_request", "detail": "too_many_unit_ids"}, status_code=400, vary_origin=True)

    sub = _current_sub(user)
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        if isinstance(guard, JSONResponse):
            guard.headers.setdefault("Cache-Control", "private, no-store")
            guard.headers.setdefault("Vary", "Origin")
            return guard
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)

    try:
        overview = _get_student_live_overview_service().build(
            course_id=course_id,
            owner_sub=sub,
            student_sub=student_sub,
            raw_unit_ids=normalized_unit_ids,
        )
    except ValueError as exc:
        return _private_error({"error": "bad_request", "detail": str(exc)}, status_code=400, vary_origin=True)
    except LookupError:
        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)

    names = _resolve_student_login_labels_runtime([str(student_sub)])
    display_name = names.get(str(student_sub), "Unbekannt")
    return _json_private(overview.to_dict(student_name=display_name), status_code=200, vary_origin=True)


async def get_latest_submission_detail(
    request: Request,
    course_id: str,
    unit_id: str,
    task_id: str,
    student_sub: str,
):
    """Latest submission detail for a student-task within a course-unit (owner-only).

    Intent:
        Allow teachers (course owners) to inspect the latest submission of a
        particular student for a given task in the selected unit, without
        exposing bulk content in the live matrix.

    Permissions:
        Caller must be a teacher and the owner of the course. Unit must belong
        to the course (best-effort verification). Returns 204 when no
        submission exists.
    """
    def _issue_h5p_review_token(
        *,
        owner_sub: str,
        course_id_in: str,
        task_id_in: str,
        student_sub_in: str,
        content_id_in: str,
    ) -> Optional[str]:
        """Return a short-lived, signed H5P review capability token.

        Why:
            The teacher review UI must load the student's H5P userState without
            exposing a generic "impersonate user" query parameter. We therefore
            issue a short-lived capability token that binds:
              - teacher (owner_sub),
              - student,
              - course,
              - task context,
              - H5P content id.

        Permissions:
            Caller must already have verified course ownership (teacher-only).
        """
        secret = (os.getenv("H5P_REVIEW_TOKEN_SECRET") or "").strip()
        if not secret:
            return None
        try:
            import base64
            import hashlib
            import hmac
            import json

            now = int(time.time())
            exp = now + 10 * 60
            payload_obj = {
                "teacher_sub": owner_sub,
                "student_sub": student_sub_in,
                "course_id": course_id_in,
                "task_id": task_id_in,
                "content_id": content_id_in,
                "exp": exp,
            }
            raw_json = json.dumps(payload_obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
            payload_b64 = base64.urlsafe_b64encode(raw_json).decode("ascii").rstrip("=")
            sig = hmac.new(secret.encode("utf-8"), raw_json, hashlib.sha256).digest()
            sig_b64 = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
            return f"{payload_b64}.{sig_b64}"
        except Exception:
            return None

    repo = _get_repo()
    user, forbidden = _require_teacher(request)
    if forbidden:
        forbidden.headers.setdefault("Cache-Control", "private, no-store")
        forbidden.headers.setdefault("Vary", "Origin")
        return forbidden
    # Validate identifiers
    if not (_is_uuid_like(course_id) and _is_uuid_like(unit_id) and _is_uuid_like(task_id)):
        return _private_error({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, vary_origin=True)

    sub = _current_sub(user)
    # Ownership guard
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        if isinstance(guard, JSONResponse):
            guard.headers.setdefault("Cache-Control", "private, no-store")
            guard.headers.setdefault("Vary", "Origin")
            return guard
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)

    # Strict verification that task belongs to unit and unit is attached to course
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        modules = []
        if isinstance(repo, DBTeachingRepo):
            modules = repo.list_course_modules_for_owner(course_id, sub)
        else:
            modules = [asdict(m) if is_dataclass(m) else m for m in repo.list_course_modules_for_owner(course_id, sub)]
        attached_unit_ids = {str(m.get("unit_id")) for m in modules}
        if str(unit_id) not in attached_unit_ids:
            return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)
    except Exception:
        # Fail closed on relation check errors
        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)

    # Query latest submission via SECURITY DEFINER helper (owner scope)
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            from backend.web.db_cursor import open_repo_cursor

            dsn = getattr(repo, "_dsn", None)
            if dsn:
                with open_repo_cursor(dsn=dsn) as (_conn, cur):
                    cur.execute("select set_config('app.current_sub', %s, true)", (sub,))
                    # Enforce task ∈ unit via explicit relation check (DB)
                    cur.execute(
                        """
                        select t.kind::text,
                               t.instruction_md,
                               t.h5p_content_id::text
                          from public.unit_tasks t
                          join public.unit_sections s on s.id = t.section_id
                          join public.course_modules m on m.unit_id = s.unit_id
                         where m.course_id = %s
                           and s.unit_id = %s::uuid
                           and t.id = %s::uuid
                         limit 1
                        """,
                        (course_id, unit_id, task_id),
                    )
                    task_row = cur.fetchone()
                    if task_row is None:
                        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)
                    task_kind, task_instruction_md, task_h5p_content_id = task_row
                    try:
                        # SECURITY DEFINER helper encapsulates owner checks and RLS-aware access
                        cur.execute(
                            """
                            select id::text,
                                   task_id::text,
                                   student_sub::text,
                                   created_at,
                                   completed_at,
                                   kind,
                                   score_raw,
                                   score_max,
                                   text_body,
                                   mime_type,
                                   size_bytes,
                                   storage_key,
                                   feedback_md,
                                   analysis_json
                              from public.get_latest_submission_for_owner(%s, %s, %s, %s, %s)
                            """,
                            (sub, course_id, unit_id, task_id, student_sub),
                        )
                    except Exception as exc:
                        logger.warning("latest submission helper unavailable — %s", exc)
                        # Safe fallback under RLS with strict relation + owner scope; may still be restricted
                        cur.execute(
                            """
                            select id::text, task_id::text, student_sub::text, created_at, completed_at, kind,
                                   score_raw, score_max,
                                   text_body, mime_type, size_bytes, storage_key, feedback_md, analysis_json
                              from public.learning_submissions
                             where course_id = %s
                               and task_id = %s::uuid
                               and student_sub = %s
                             order by created_at desc, attempt_nr desc, id desc
                             limit 1
                            """,
                            (course_id, task_id, student_sub),
                        )
                    row = cur.fetchone()
                    if not row:
                        return Response(status_code=204, headers={"Cache-Control": "private, no-store", "Vary": "Origin"})
                    (
                        sid,
                        tid,
                        ssub,
                        created_at,
                        completed_at,
                        kind,
                        score_raw,
                        score_max,
                        text_body,
                        mime_type,
                        size_bytes,
                        storage_key,
                        feedback_md,
                        analysis_json,
                    ) = row
                    review_token = None
                    if str(kind or "") == "h5p" and isinstance(task_h5p_content_id, str) and task_h5p_content_id:
                        review_token = _issue_h5p_review_token(
                            owner_sub=str(sub),
                            course_id_in=str(course_id),
                            task_id_in=str(task_id),
                            student_sub_in=str(student_sub),
                            content_id_in=str(task_h5p_content_id),
                        )
                    payload = _build_latest_submission_payload(
                        course_id=str(course_id),
                        unit_id=str(unit_id),
                        file_href_builder=_teaching_submission_file_href,
                        sid=sid,
                        tid=tid,
                        ssub=ssub,
                        instruction_md=task_instruction_md,
                        created_at=created_at,
                        completed_at=completed_at,
                        kind=kind,
                        score_raw=score_raw,
                        score_max=score_max,
                        h5p_content_id=(task_h5p_content_id if str(task_kind or "") == "h5p" else None),
                        h5p_review_token=review_token,
                        text_body=text_body,
                        mime_type=mime_type,
                        size_bytes=size_bytes,
                        storage_key=storage_key,
                        feedback_md=feedback_md,
                        analysis_json=analysis_json,
                        include_files=True,
                    )
                    return _json_private(payload, status_code=200, vary_origin=True)
    except Exception as exc:
        logger.warning("latest submission query failed — %s", exc, extra={"course_id": course_id, "task_id": task_id})
        # Defensive fallback: when helper or extended query fails (e.g. during migrations),
        # try a minimal direct lookup that only relies on the core columns.
        try:
            from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
            if isinstance(repo, DBTeachingRepo):
                from backend.web.db_cursor import open_repo_cursor

                dsn = getattr(repo, "_dsn", None)
                if dsn:
                    with open_repo_cursor(dsn=dsn) as (_conn, cur):
                        cur.execute("select set_config('app.current_sub', %s, true)", (sub,))
                        # Re-apply the strict task ∈ unit ∈ course relation check in the
                        # fallback path as well so mismatched unit/task combinations still
                        # fail with 404 instead of accidentally leaking submissions.
                        cur.execute(
                            """
                            select t.kind::text,
                                   t.instruction_md,
                                   t.h5p_content_id::text
                              from public.unit_tasks t
                              join public.unit_sections s on s.id = t.section_id
                              join public.course_modules m on m.unit_id = s.unit_id
                             where m.course_id = %s
                               and s.unit_id = %s::uuid
                               and t.id = %s::uuid
                             limit 1
                            """,
                            (course_id, unit_id, task_id),
                        )
                        task_row = cur.fetchone()
                        if task_row is None:
                            return _private_error(
                                {"error": "not_found"}, status_code=404, vary_origin=True
                            )
                        task_kind, task_instruction_md, task_h5p_content_id = task_row
                        cur.execute(
                            """
                            select id::text,
                                   task_id::text,
                                   student_sub::text,
                                   created_at,
                                   completed_at,
                                   kind,
                                   score_raw,
                                   score_max,
                                   text_body,
                                   mime_type,
                                   size_bytes,
                                   storage_key,
                                   feedback_md,
                                   analysis_json
                              from public.learning_submissions
                             where course_id = %s
                               and task_id = %s::uuid
                               and student_sub = %s
                             order by created_at desc, attempt_nr desc, id desc
                             limit 1
                            """,
                            (course_id, task_id, student_sub),
                        )
                        row = cur.fetchone()
                        if not row:
                            return Response(
                                status_code=204,
                                headers={"Cache-Control": "private, no-store", "Vary": "Origin"},
                            )
                        (
                            sid,
                            tid,
                            ssub,
                            created_at,
                            completed_at,
                            kind,
                            score_raw,
                            score_max,
                            text_body,
                            mime_type,
                            size_bytes,
                            storage_key,
                            feedback_md,
                            analysis_json,
                        ) = row
                        review_token = None
                        if str(kind or "") == "h5p" and isinstance(task_h5p_content_id, str) and task_h5p_content_id:
                            review_token = _issue_h5p_review_token(
                                owner_sub=str(sub),
                                course_id_in=str(course_id),
                                task_id_in=str(task_id),
                                student_sub_in=str(student_sub),
                                content_id_in=str(task_h5p_content_id),
                            )
                        payload = _build_latest_submission_payload(
                            course_id=str(course_id),
                            unit_id=str(unit_id),
                            file_href_builder=_teaching_submission_file_href,
                            sid=sid,
                            tid=tid,
                            ssub=ssub,
                            instruction_md=task_instruction_md,
                            created_at=created_at,
                            completed_at=completed_at,
                            kind=kind,
                            score_raw=score_raw,
                            score_max=score_max,
                            h5p_content_id=(task_h5p_content_id if str(task_kind or "") == "h5p" else None),
                            h5p_review_token=review_token,
                            text_body=text_body,
                            mime_type=mime_type,
                            size_bytes=size_bytes,
                            storage_key=storage_key,
                            feedback_md=feedback_md,
                            analysis_json=analysis_json,
                            include_files=False,
                        )
                        return _json_private(payload, status_code=200, vary_origin=True)
        except Exception:
            # Conservatively fall through to 204 when even the direct lookup fails.
            pass

    # Fallback when DB path not available or no submission was found
    return Response(status_code=204, headers={"Cache-Control": "private, no-store", "Vary": "Origin"})


async def get_teaching_submission_file(
    request: Request,
    course_id: str,
    unit_id: str,
    task_id: str,
    student_sub: str,
    disposition: Optional[str] = None,
):
    """Stream a teacher-visible submission file through a stable same-origin route."""

    user, forbidden = _require_teacher(request)
    if forbidden:
        forbidden.headers.setdefault("Cache-Control", "private, no-store")
        forbidden.headers.setdefault("Vary", "Origin")
        return forbidden

    if not (_is_uuid_like(course_id) and _is_uuid_like(unit_id) and _is_uuid_like(task_id)):
        return _private_error({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, vary_origin=True)

    normalized_disposition = (disposition or "inline").strip().lower()
    if normalized_disposition not in {"inline", "attachment"}:
        return _private_error({"error": "bad_request", "detail": "invalid_disposition"}, status_code=400, vary_origin=True)

    sub = _current_sub(user)
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
        if not isinstance(repo, DBTeachingRepo):
            return _private_error({"error": "service_unavailable"}, status_code=503, vary_origin=True)

        from backend.web.db_cursor import open_repo_cursor

        dsn = getattr(repo, "_dsn", None)
        if not dsn:
            return _private_error({"error": "service_unavailable"}, status_code=503, vary_origin=True)

        with open_repo_cursor(dsn=dsn) as (_conn, cur):
            cur.execute("select set_config('app.current_sub', %s, true)", (sub,))
            cur.execute(
                """
                select exists(
                         select 1
                           from public.course_modules
                          where course_id = %s
                            and unit_id = %s::uuid
                     )
                """,
                (course_id, unit_id),
            )
            if not bool((cur.fetchone() or [False])[0]):
                return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)
            cur.execute(
                """
                select s.mime_type,
                       s.size_bytes,
                       s.storage_key
                  from public.get_latest_submission_for_owner(%s, %s, %s, %s, %s) s
                 where s.id::text is not null
                 limit 1
                """,
                (sub, course_id, unit_id, task_id, student_sub),
            )
            row = cur.fetchone()
    except Exception:
        row = None

    if not row:
        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)

    mime_type, size_bytes_raw, storage_key = row
    mime_type = str(mime_type or "").strip().lower()
    storage_key = str(storage_key or "").strip()
    try:
        size_bytes = max(0, int(size_bytes_raw or 0))
    except (TypeError, ValueError):
        size_bytes = 0
    if not mime_type or not storage_key:
        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)

    try:
        from backend.web.routes import learning as learning_routes  # type: ignore

        adapter = getattr(learning_routes, "STORAGE_ADAPTER", STORAGE_ADAPTER)
    except Exception:
        adapter = STORAGE_ADAPTER

    if adapter is None or isinstance(adapter, NullStorageAdapter):
        return _private_error({"error": "service_unavailable"}, status_code=503, vary_origin=True)

    try:
        presigned = adapter.presign_download(  # type: ignore[union-attr]
            bucket=get_submissions_bucket(),
            key=storage_key,
            expires_in=60,
            disposition=normalized_disposition,
        )
    except Exception:
        presigned = None

    url = str((presigned or {}).get("url") or "").strip()
    headers = (presigned or {}).get("headers") if isinstance(presigned, dict) else None
    try:
        forward_headers = {str(k): str(v) for k, v in dict(headers or {}).items() if k and v}
    except Exception:
        forward_headers = None
    if not url:
        return _private_error({"error": "service_unavailable"}, status_code=503, vary_origin=True)

    downloader = _current_download_bytes_with_limit()
    body = await downloader(url=url, max_bytes=max(10 * 1024 * 1024, size_bytes), headers=forward_headers)
    if body is None:
        return _private_error({"error": "service_unavailable"}, status_code=503, vary_origin=True)

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
