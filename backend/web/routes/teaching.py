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

import os
import sys as _sys
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse

from backend.teaching.services.materials import MaterialFileSettings, MaterialsService
from backend.teaching.services.live_student_overview import MAX_UNIT_IDS, StudentLiveOverviewService
from backend.teaching.repo_row_mappers import compute_average_score_from_analysis  # noqa: F401
from backend.teaching.storage import NullStorageAdapter, StorageAdapterProtocol
from backend.web.routes.teaching_shared import (
    _is_uuid_like,
    _private_error,
)
from backend.web.routes.teaching_task_services import (
    configure_task_service_repo_provider,
)
from backend.web.routes.teaching_authoring import (
    _is_signature_compat_type_error,
    configure_teaching_authoring_repo_provider,
)
from backend.web.routes.teaching_guards import (
    configure_teaching_guard_repo_provider,
)
from backend.web.routes.teaching_validation import canonical_uuid as _canonical_uuid
from backend.web.routes import (
    teaching_course_state,
    teaching_payloads,
    teaching_serialization,
    teaching_storage_cleanup,
    teaching_submission_files,
    teaching_validation,
)
from backend.web.routes.teaching_storage_cleanup import (
    metadata_page_keys as _metadata_page_keys,  # noqa: F401 - kept for route module compatibility
    unit_delete_storage_metadata_dsn as _unit_delete_storage_metadata_dsn,  # noqa: F401
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
_build_latest_submission_payload = teaching_serialization._build_latest_submission_payload
_build_live_delta_cells = teaching_serialization._build_live_delta_cells
_build_live_summary_rows = teaching_serialization._build_live_summary_rows
_serialize_unit_graph_edge = teaching_serialization._serialize_unit_graph_edge
_serialize_unit_module = teaching_serialization._serialize_unit_module
_serialize_unit_phase_public = teaching_serialization._serialize_unit_phase_public
_safe_int = teaching_validation.safe_int
_download_bytes_with_limit = teaching_submission_files.download_bytes_with_limit
_safe_download_filename = teaching_submission_files.safe_download_filename
_teaching_submission_file_href = teaching_submission_files.teaching_submission_file_href


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
_MOVED_LIVE_HANDLER_NAMES = frozenset(
    {
        "get_unit_live_summary",
        "get_unit_live_delta",
        "get_student_live_overview",
        "get_latest_submission_detail",
        "get_teaching_submission_file",
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
    if name in _MOVED_LIVE_HANDLER_NAMES:
        from backend.web.routes import teaching_live

        return getattr(teaching_live, name)
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

# Live handlers live in backend.web.routes.teaching_live.
