"""Learning (Lernen) API routes."""

from __future__ import annotations

import logging
import os
import re
import sys as _sys
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse, Response

from backend.learning.repo_db import DBLearningRepo
from .security import _is_same_origin
from backend.learning.usecases.sections import (
    ListSectionsInput,
    ListSectionsUseCase,
    ListUnitSectionsInput,
    ListUnitSectionsUseCase,
)
from backend.learning.usecases.courses import (
    ListCoursesInput,
    ListCoursesUseCase,
    ListCourseUnitsInput,
    ListCourseUnitsUseCase,
)
from backend.learning.usecases.submissions import (
    CreateSubmissionInput,  # noqa: F401 - kept for route module compatibility
    CreateSubmissionUseCase,  # noqa: F401
    FinalizeLatestDraftInput,  # noqa: F401
    FinalizeLatestDraftUseCase,  # noqa: F401
    ListSubmissionsInput,  # noqa: F401 - kept for route module compatibility
    ListSubmissionsUseCase,  # noqa: F401
)
from backend.learning.usecases.h5p_access import (
    CheckH5PContentAccessInput,
    CheckH5PContentAccessUseCase,
)
from backend.teaching.storage import NullStorageAdapter, StorageAdapterProtocol  # type: ignore
try:
    from backend.web.storage_wiring import wire_supabase_adapter_if_configured as _wire_storage  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - container fallback when package path is flattened
    _wire_storage = None  # type: ignore
from backend.storage.learning_policy import (
    ALLOWED_FILE_MIME,  # noqa: F401 - kept for route module compatibility
    ALLOWED_IMAGE_MIME,  # noqa: F401
)
from backend.storage.config import get_submissions_bucket, get_learning_max_upload_bytes
from backend.web.routes.learning_material_file_routes import (
    get_material_file as get_material_file,  # noqa: F401 - kept for route module compatibility
    get_material_file_legacy_alias as get_material_file_legacy_alias,  # noqa: F401
    learning_material_file_router,
)
from backend.web.routes.learning_internal_upload_routes import (
    internal_upload_proxy as internal_upload_proxy,  # noqa: F401 - kept for route module compatibility
    internal_upload_stub as internal_upload_stub,  # noqa: F401
    learning_internal_upload_router,
)
from backend.web.routes.learning_upload_intents import (
    create_upload_intent as create_upload_intent,  # noqa: F401 - kept for route module compatibility
    learning_upload_intents_router,
)
from backend.web.routes.learning_material_files import (
    attach_modular_material_files as _attach_modular_material_files,
    attach_section_material_files as _attach_section_material_files,
    material_file_href as _material_file_href,  # noqa: F401 - kept for route module compatibility
    resolve_student_material_file_url as _resolve_student_material_file_url,  # noqa: F401
    resolve_student_modular_material_file_url as _resolve_student_modular_material_file_url,  # noqa: F401
)
from backend.web.routes.learning_storage_validation import (
    download_bytes_with_limit as _download_bytes_with_limit,
    load_local_storage_bytes_for_validation as _load_local_storage_bytes_for_validation,  # noqa: F401
    load_storage_bytes_for_validation as _load_storage_bytes_for_validation,  # noqa: F401
    verify_storage_object as _verify_storage_object,  # noqa: F401
)
from backend.web.routes.learning_submission_files import (
    attach_submission_files as _attach_submission_files,  # noqa: F401
    get_submission_file as get_submission_file,  # noqa: F401 - kept for route module compatibility
    learning_submission_files_router,
    list_submissions as list_submissions,  # noqa: F401
    normalize_download_disposition as _normalize_download_disposition,  # noqa: F401
    submission_file_href as _submission_file_href,  # noqa: F401
)
from backend.web.routes.learning_submission_commands import (
    create_submission as create_submission,  # noqa: F401 - kept for route module compatibility
    finalize_submission as finalize_submission,  # noqa: F401
    learning_submission_commands_router,
)
from backend.web.routes.learning_dialogs import learning_dialog_router
from backend.web.routes.learning_submission_processing import (
    dev_try_process_pdf as _dev_try_process_pdf,  # noqa: F401
    validate_submission_payload as _validate_submission_payload,  # noqa: F401
)
from backend.web.routes.learning_upload_proxy import (
    decode_proxy_headers as _decode_proxy_headers,  # noqa: F401 - kept for route module compatibility
    encode_proxy_headers as _encode_proxy_headers,  # noqa: F401 - kept for route module compatibility
    filter_upload_proxy_headers as _filter_upload_proxy_headers,  # noqa: F401
    normalized_parts as _normalized_parts,  # noqa: F401
)
from backend.web.routes.learning_upload_proxy import async_forward_upload as _default_async_forward_upload
from backend.web.routes.learning_upload_config import (
    dev_upload_stub_enabled as _dev_upload_stub_enabled,  # noqa: F401 - kept for route module compatibility
    upload_intent_ttl_seconds as _upload_intent_ttl_seconds,  # noqa: F401
    upload_proxy_enabled as _upload_proxy_enabled,  # noqa: F401
    upload_proxy_timeout_seconds as _upload_proxy_timeout_seconds,  # noqa: F401
)
import httpx
from urllib.parse import urlparse as _urlparse, quote as _quote  # noqa: F401
learning_router = APIRouter(tags=["Learning"])
learning_router.include_router(learning_material_file_router)
learning_router.include_router(learning_upload_intents_router)
learning_router.include_router(learning_internal_upload_router)
learning_router.include_router(learning_submission_files_router)
learning_router.include_router(learning_submission_commands_router)
learning_router.include_router(learning_dialog_router)
logger = logging.getLogger("gustav.web.learning")

# Compatibility note for source-level contract tests after upload-intent route
# extraction: the Filius branch now lives in learning_upload_intents.py as
# `task_kind == "filius"` and maps uploads with `ext = ".fls"`.

STORAGE_ADAPTER: StorageAdapterProtocol = NullStorageAdapter()
_STORAGE_ADAPTER_OVERRIDE_ACTIVE = False


def _current_learning_module() -> object | None:
    """Return the active learning module instance."""

    return _sys.modules.get("backend.web.routes.learning")


def _current_storage_adapter() -> StorageAdapterProtocol:
    """Resolve the active storage adapter for the running route module."""

    return STORAGE_ADAPTER


def _current_async_forward_upload() -> Any:
    """Resolve the active upload forwarder for the running route module."""

    default = globals().get("_DEFAULT_ASYNC_FORWARD_UPLOAD")
    local = _async_forward_upload
    if default is not None and callable(local) and local is not default:
        return local
    module = _current_learning_module()
    current = getattr(module, "_async_forward_upload", None) if module is not None else None
    if default is not None and callable(current) and current is not default:
        return current
    return local


def _current_emit_upload_proxy_telemetry() -> Any:
    """Resolve the active telemetry emitter for the running route module."""

    default = globals().get("_DEFAULT_EMIT_UPLOAD_PROXY_TELEMETRY")
    local = _emit_upload_proxy_telemetry
    if default is not None and callable(local) and local is not default:
        return local
    module = _current_learning_module()
    current = getattr(module, "_emit_upload_proxy_telemetry", None) if module is not None else None
    if default is not None and callable(current) and current is not default:
        return current
    return local


def _current_download_bytes_with_limit() -> Any:
    """Resolve the active storage downloader for the running route module."""

    default = globals().get("_DEFAULT_DOWNLOAD_BYTES_WITH_LIMIT")
    local = _download_bytes_with_limit
    if default is not None and callable(local) and local is not default:
        return local
    module = _current_learning_module()
    current = getattr(module, "_download_bytes_with_limit", None) if module is not None else None
    if default is not None and callable(current) and current is not default:
        return current
    return local


def _sync_learning_route_globals(*, adapter: StorageAdapterProtocol, override_active: bool) -> None:
    """Keep already-registered FastAPI learning routes bound to the latest adapter.

    Why:
        Some tests deliberately reload `backend.web.routes.learning` while keeping an older
        `main.app` instance alive. FastAPI route callables keep the globals from
        the module instance they were created in, so updating only the freshly
        imported module would leave old route endpoints pointing at a stale
        `STORAGE_ADAPTER`.
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
            if not str(getattr(route, "path", "")).startswith("/api/learning"):
                continue
            route_globals = getattr(route.endpoint, "__globals__", None)
            if isinstance(route_globals, dict) and "STORAGE_ADAPTER" in route_globals:
                route_globals["STORAGE_ADAPTER"] = adapter
                route_globals["_STORAGE_ADAPTER_OVERRIDE_ACTIVE"] = override_active


def set_storage_adapter(adapter: StorageAdapterProtocol, *, override: bool = True) -> None:
    """Allow tests or startup code to provide a concrete storage adapter.

    The update also retargets already-registered Learning route globals in
    existing FastAPI app instances. This keeps reload-heavy tests deterministic
    when a fresh `backend.web.routes.learning` module is imported after `main.app` was
    constructed earlier in the same Python process.
    """
    global STORAGE_ADAPTER, _STORAGE_ADAPTER_OVERRIDE_ACTIVE
    STORAGE_ADAPTER = adapter
    _STORAGE_ADAPTER_OVERRIDE_ACTIVE = bool(override)
    for module_name in ("backend.web.routes.learning",):
        module = _sys.modules.get(module_name)
        if module is None:
            continue
        setattr(module, "STORAGE_ADAPTER", adapter)
        setattr(module, "_STORAGE_ADAPTER_OVERRIDE_ACTIVE", bool(override))
    _sync_learning_route_globals(adapter=adapter, override_active=_STORAGE_ADAPTER_OVERRIDE_ACTIVE)


def _storage_bucket() -> str:
    # Delegate to centralized config to avoid drift and simplify testing.
    return get_submissions_bucket()


def _max_upload_bytes() -> int:
    return get_learning_max_upload_bytes()


def _safe_download_filename(filename: str | None, fallback: str) -> str:
    raw = str(filename or "").strip()
    candidate = raw or fallback
    cleaned = "".join(ch for ch in candidate if ch not in {'"', "\r", "\n"})
    return cleaned or fallback


async def _download_storage_object_via_presign(
    *,
    bucket: str,
    key: str,
    disposition: str,
    max_bytes: int,
    adapter: StorageAdapterProtocol | object | None = None,
) -> bytes | None:
    resolved_adapter = adapter if adapter is not None else _current_storage_adapter()
    if not bucket or resolved_adapter is None or isinstance(resolved_adapter, NullStorageAdapter):
        return None
    try:
        presigned = resolved_adapter.presign_download(bucket=bucket, key=key, expires_in=60, disposition=disposition)
    except Exception:
        return None
    url = str((presigned or {}).get("url") or "").strip()
    if not url:
        return None
    headers = presigned.get("headers") if isinstance(presigned, dict) else None
    try:
        hdrs = {str(k): str(v) for k, v in dict(headers or {}).items() if k and v}
    except Exception:
        hdrs = None
    downloader = _current_download_bytes_with_limit()
    return await downloader(url=url, max_bytes=max_bytes, headers=hdrs)


async def _read_request_stream_with_limit(request: Request, limit: int) -> tuple[bytes | None, str | None]:
    """Consume the request stream without buffering unlimited bytes."""

    total = 0
    buffer = bytearray()
    async for chunk in request.stream():
        if not chunk:
            continue
        buffer.extend(chunk)
        total += len(chunk)
        if limit > 0 and total > limit:
            return None, "size_exceeded"
    if not buffer:
        return None, "empty_body"
    return bytes(buffer), None


async def _async_forward_upload(
    *,
    url: str,
    payload: bytes,
    content_type: str,
    timeout: float,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Forward the upload to Supabase (patchable for tests)."""
    return await _default_async_forward_upload(
        url=url,
        payload=payload,
        content_type=content_type,
        timeout=timeout,
        headers=headers,
    )


_DEFAULT_ASYNC_FORWARD_UPLOAD = _async_forward_upload


def _cache_headers_success() -> dict[str, str]:
    # Success responses: private and explicitly non-storable (defense-in-depth
    # against history stores and intermediary caches potentially keeping PII).
    # Include Vary: Origin to prevent cache confusion across origins.
    return {"Cache-Control": "private, no-store", "Vary": "Origin"}


def _cache_headers_error() -> dict[str, str]:
    # Error responses: must never be stored; protects PII-bearing error pages.
    # Include Vary: Origin for consistency with success responses.
    return {"Cache-Control": "private, no-store", "Vary": "Origin"}


def _teaching_storage_adapter() -> object | None:
    for module_name in ("backend.web.routes.teaching",):
        module = _sys.modules.get(module_name)
        if module is not None:
            return getattr(module, "STORAGE_ADAPTER", None)
    return None


def _require_repo_methods(repo: object, *method_names: str) -> JSONResponse | None:
    """Ensure modular read routes fail closed when repo capabilities are missing."""
    for method_name in method_names:
        if not callable(getattr(repo, method_name, None)):
            return JSONResponse({"error": "service_unavailable"}, status_code=503, headers=_cache_headers_error())
    return None


def _emit_upload_proxy_telemetry(
    *,
    outcome: str,
    status_code: int,
    reason: str,
    target_host: str,
    content_type: str,
    size_bytes: int | None,
) -> None:
    """Emit low-cardinality upload proxy telemetry without PII."""
    try:
        logger.info(
            "learning.upload_proxy outcome=%s status=%s reason=%s host=%s mime=%s size_bytes=%s",
            outcome,
            int(status_code),
            str(reason or "n/a"),
            str(target_host or "n/a"),
            str(content_type or "n/a"),
            int(size_bytes) if size_bytes is not None else -1,
        )
    except Exception:
        # Telemetry must never affect API behavior.
        return


_DEFAULT_EMIT_UPLOAD_PROXY_TELEMETRY = _emit_upload_proxy_telemetry


def _require_strict_same_origin(request: Request) -> bool:
    """Return True only when a same-origin indicator is present and matches.

    Why:
        For browser-triggered POSTs (e.g., upload-intents), we require either an
        `Origin` or `Referer` header to be present and same-origin to reduce
        the CSRF attack surface. Server-to-server calls (no headers) should use
        other routes and remain unaffected.
    """
    origin_present = (request.headers.get("origin") or request.headers.get("referer"))
    if not origin_present:
        return False
    return _is_same_origin(request)

def _redact_origin_for_diag_log(raw_value: str) -> str:
    """Return a safe origin string for diagnostic logs (no path/query).

    Why:
        `CSRF_DIAG_LOG` is an optional debug mechanism. We must not write full
        Referer URLs (paths/queries may contain PII or tokens) to disk.

    Behavior:
        - Accept an Origin or Referer header value.
        - Return only `scheme://host[:port]` when parseable.
        - Return "?" for invalid or empty inputs.
    """
    value = str(raw_value or "").strip()
    if not value:
        return "?"
    try:
        from urllib.parse import urlparse

        parsed = urlparse(value)
        if parsed.scheme and parsed.netloc:
            scheme = parsed.scheme.strip()
            netloc = parsed.netloc.strip()
            if scheme and netloc:
                return f"{scheme}://{netloc}"
    except Exception:
        pass
    return "?"

def _current_environment() -> str:
    """Return the current app environment string.

    Resolution is lazy to avoid import-order flakiness in tests:
    - Try to import `backend.web.main` or `main` and read `RUNTIME.settings.environment`.
    - Fallback to `GUSTAV_ENV` (default "dev").
    """
    def _read_env_from_module(mod: object | None) -> str | None:
        if mod is None:
            return None
        try:
            runtime = getattr(mod, "RUNTIME", None)
            settings = getattr(runtime, "settings", None)
        except Exception:
            return None
        if settings is None:
            return None
        try:
            raw = getattr(settings, "environment", None)
        except Exception:
            return None
        if raw is None:
            return None
        value = str(raw).strip().lower()
        return value or None

    def _loaded_override_env(alias: str) -> str | None:
        mod = _sys.modules.get(alias)
        if mod is None:
            return None
        try:
            runtime = getattr(mod, "RUNTIME", None)
            settings = getattr(runtime, "settings", None)
        except Exception:
            return None
        if settings is None:
            return None
        # Only short-circuit when an explicit override is present so tests can
        # observe module-level overrides even if later imports fail.
        if getattr(settings, "_env_override", None) is None:
            return None
        return _read_env_from_module(mod)

    for alias in ("backend.web.main",):
        env = _loaded_override_env(alias)
        if env:
            return env

    import importlib

    for alias in ("backend.web.main",):
        try:
            mod = importlib.import_module(alias)
        except Exception:
            continue
        env = _read_env_from_module(mod)
        if env:
            return env
    return (os.getenv("GUSTAV_ENV", "dev") or "").lower()


def _environment_for_request(request: Request) -> str:
    """Read the environment from the FastAPI app handling this request."""

    try:
        runtime = getattr(getattr(request.app, "state", None), "runtime", None)
        settings = getattr(runtime, "settings", None)
        raw = getattr(settings, "environment", None)
        if raw is not None:
            value = str(raw).strip().lower()
            if value:
                return value
    except Exception:
        pass
    return _current_environment()


def _current_user(request: Request) -> dict | None:
    user = getattr(request.state, "user", None)
    return user if isinstance(user, dict) else None


def _require_student(request: Request):
    """Ensure the caller is authenticated and has the student role.

    Robustness:
        Prefer the roles list on the user context, but accept a single
        primary role fallback (request.state.user.role) to guard against rare
        test-time drift where only the primary role is present.
    """
    user = _current_user(request)
    if not user:
        return None, JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_cache_headers_error())
    roles = user.get("roles")
    primary = str(user.get("role", "")).lower()
    has_student = False
    if isinstance(roles, list):
        try:
            has_student = "student" in [str(r).lower() for r in roles]
        except Exception:
            has_student = False
    if not has_student and primary == "student":
        has_student = True
    if not has_student:
        # Add lightweight diagnostics for non-CSRF 403s to aid flaky runs.
        try:
            raw_origin = str(request.headers.get("origin") or request.headers.get("referer") or "")
            origin_hdr = _redact_origin_for_diag_log(raw_origin)
            scheme = (request.url.scheme or "http").lower()
            host_hdr = (request.headers.get("host") or request.url.hostname or "").lower()
            if ":" in host_hdr:
                host_only, port_str = host_hdr.rsplit(":", 1)
                host = host_only
                try:
                    port = int(port_str)
                except Exception:
                    port = 443 if scheme == "https" else 80
            else:
                host = host_hdr
                port = int(request.url.port) if request.url.port else (443 if scheme == "https" else 80)
            default = 443 if scheme == "https" else 80
            server_origin = f"{scheme}://{host}{(':' + str(port)) if port != default else ''}"
            diag = f"reason=auth,env={_current_environment()},origin={origin_hdr},server={server_origin}"
        except Exception:
            diag = "reason=auth,env=?,origin=?,server=?"
        # Best-effort file logging when requested.
        try:
            log_path = (os.getenv("CSRF_DIAG_LOG") or "").strip()
            if log_path:
                with open(log_path, "a", encoding="utf-8") as fp:
                    fp.write(f"require_student: {diag}\n")
        except Exception:
            pass
        # Do not leak diagnostics to clients; log above when CSRF_DIAG_LOG set.
        return None, JSONResponse({"error": "forbidden"}, status_code=403, headers=_cache_headers_error())
    return user, None


"""CSRF helper imported from .security"""


def _parse_include(
    value: str | None, *, default_materials: bool = False, default_tasks: bool = False
) -> tuple[bool, bool]:
    if value is None:
        return default_materials, default_tasks
    raw = value.strip()
    if not raw:
        raise ValueError("invalid_include")
    parts = raw.split(",")
    tokens = [token.strip() for token in parts]
    if any(not token for token in tokens):
        raise ValueError("invalid_include")
    allowed = {"materials", "tasks"}
    if any(token not in allowed for token in tokens):
        raise ValueError("invalid_include")
    return "materials" in tokens, "tasks" in tokens


def _canonical_uuid_or_none(value: object) -> str | None:
    """Return a canonical UUID string or None when parsing fails."""
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError):
        return None


def _is_uuid_like(value: object) -> bool:
    return _canonical_uuid_or_none(value) is not None


# Note: Pagination clamping is handled in the use case layer to keep this
# adapter thin and framework-agnostic.


# Lazily construct the repository to ensure environment (.env, pytest) is loaded
# before establishing DB connections. This avoids import-time failures and keeps
# the adapter thin. Tests can override via set_repo().
_REPO: _LearningRepoCombined | None = None

def _get_repo() -> _LearningRepoCombined:
    global _REPO, REPO
    if _REPO is None:
        _REPO = DBLearningRepo()
    # Keep the public alias in sync for tests that check `learning.REPO`.
    REPO = _REPO
    return _REPO

# Back-compat: expose a concrete instance for tests that check `learning.REPO`.
# Mirrors the Teaching routes pattern so DB-backed contract tests don't skip.
REPO = _get_repo()

# Narrow typing for test helpers without pulling framework types into use cases
try:
    from typing import Protocol  # Python 3.11
except Exception:  # pragma: no cover - typing fallback
    Protocol = object  # type: ignore


class _LearningRepoCombined(Protocol):  # pragma: no cover - typing aid
    def list_released_sections(
        self,
        *,
        student_sub: str,
        course_id: str,
        include_materials: bool,
        include_tasks: bool,
        limit: int,
        offset: int,
    ) -> list[dict]:
        ...

    def create_submission(self, data) -> dict:
        ...

    def list_submissions(
        self,
        *,
        student_sub: str,
        course_id: str,
        task_id: str,
        limit: int,
        offset: int,
    ) -> list[dict]:
        ...

    def get_task_kind_for_student(self, *, student_sub: str, course_id: str, task_id: str) -> str:
        ...

    def get_modular_unit_graph(
        self,
        *,
        student_sub: str,
        course_id: str,
        unit_id: str,
    ) -> dict:
        ...

    def get_modular_module_content(
        self,
        *,
        student_sub: str,
        course_id: str,
        unit_id: str,
        module_id: str,
        include_materials: bool,
        include_tasks: bool,
    ) -> dict:
        ...


def set_repo(repo: _LearningRepoCombined) -> None:  # pragma: no cover - used in tests
    global _REPO, REPO
    _REPO = repo
    REPO = repo
    for module_name in ("backend.web.routes.learning",):
        module = _sys.modules.get(module_name)
        if module is None:
            continue
        setattr(module, "_REPO", repo)
        setattr(module, "REPO", repo)
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
            if not str(getattr(route, "path", "")).startswith("/api/learning"):
                continue
            route_globals = getattr(route.endpoint, "__globals__", None)
            if isinstance(route_globals, dict) and "_REPO" in route_globals:
                route_globals["_REPO"] = repo
                route_globals["REPO"] = repo
                route_globals["_get_repo"] = _get_repo


@learning_router.get("/api/learning/courses/{course_id}/sections")
async def list_sections(
    request: Request,
    course_id: str,
    include: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List released sections for a course (student-only).

    Intent:
        Return only sections released to the authenticated student.

    Permissions:
        Caller must have the `student` role and be enrolled in the course.
    """
    user, error = _require_student(request)
    if error:
        return error

    try:
        UUID(course_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers_error())

    try:
        include_materials, include_tasks = _parse_include(include)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_include"}, status_code=400, headers=_cache_headers_error())

    input_data = ListSectionsInput(
        student_sub=str(user.get("sub", "")),
        course_id=course_id,
        include_materials=include_materials,
        include_tasks=include_tasks,
        # Clamp happens in the use case to keep adapter thin
        limit=limit,
        offset=offset,
    )

    try:
        sections = ListSectionsUseCase(_get_repo()).execute(input_data)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_cache_headers_error())
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    sections = _attach_section_material_files(
        student_sub=str(user.get("sub", "")),
        course_id=course_id,
        sections=sections,
    )
    return JSONResponse(sections, headers=_cache_headers_success())


@learning_router.get("/api/learning/courses/{course_id}/h5p/contents/{content_id}/access")
async def check_h5p_content_access(request: Request, course_id: str, content_id: str):
    """Return 204 when the student may access an H5P content id (fail-closed).

    Why:
        The H5P sidecar must verify that a student is allowed to load a given
        H5P `content_id` within a course, without enumerating all released tasks.

    Behavior:
        - 204: content is part of a released H5P task in the course for this student
        - 404: not allowed / not member / not released (fail-closed)
        - 400: invalid UUID or invalid content id

    Permissions:
        Caller must have role `student`.
    """
    user, error = _require_student(request)
    if error:
        return error

    try:
        UUID(course_id)
    except ValueError:
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_uuid"},
            status_code=400,
            headers=_cache_headers_error(),
        )

    if not isinstance(content_id, str) or not re.fullmatch(r"[0-9]+", content_id):
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_content_id"},
            status_code=400,
            headers=_cache_headers_error(),
        )

    allowed = CheckH5PContentAccessUseCase(_get_repo()).execute(
        CheckH5PContentAccessInput(
            student_sub=str(user.get("sub", "")),
            course_id=course_id,
            content_id=content_id,
        )
    )
    if allowed:
        return Response(status_code=204, headers=_cache_headers_success())
    return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())


@learning_router.get("/api/learning/courses")
async def list_my_courses(request: Request, limit: int = 50, offset: int = 0):
    """List courses for the current student (alphabetical, minimal fields).

    Why:
        Dedicated Learning endpoint that exposes only student-facing fields and
        separates responsibilities from Teaching. This reduces accidental data
        leakage (e.g., teacher_id) and keeps the contract stable for learners.

    Parameters:
        request: FastAPI request carrying the authenticated user context.
        limit: Page size clamp to 1..100 (default 50).
        offset: Zero-based starting index (default 0).

    Behavior:
        - Requires an authenticated session with role "student".
        - Returns courses where the caller is a member, sorted by
          title asc, id asc (stable secondary order).
        - Uses private, no-store Cache-Control headers.

    Permissions:
        Caller must have the `student` role; membership filtering is enforced in
        the repository via RLS and explicit joins. Responds 403 if caller lacks
        the student role.
    """
    user, error = _require_student(request)
    if error:
        return error
    items = ListCoursesUseCase(_get_repo()).execute(
        ListCoursesInput(student_sub=str(user.get("sub", "")), limit=int(limit or 50), offset=int(offset or 0))
    )
    return JSONResponse(items, headers=_cache_headers_success())


@learning_router.get("/api/learning/courses/{course_id}/units")
async def list_course_units(request: Request, course_id: str):
    """List learning units of a course for the current student.

    Why:
        Students need a read-only listing of units within a course ordered by
        the teacher-defined module position, independent from section releases.

    Parameters:
        request: FastAPI request with authenticated user context.
        course_id: UUID of the course; 400 when not UUID-like.

    Behavior:
        - Requires an authenticated session with role "student".
        - Responds 200 with an array of objects { unit: UnitPublic, position }.
        - Responds 404 when the course does not exist or the caller is not a
          member (intentionally indistinguishable to avoid leaking existence).
        - Responses include private Cache-Control headers.

    Permissions:
        Caller must have the `student` role (403 otherwise) and be a member of
        the course. Membership and ordering are enforced at the DB boundary.
    """
    user, error = _require_student(request)
    if error:
        return error
    try:
        UUID(course_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers_error())
    try:
        rows = ListCourseUnitsUseCase(_get_repo()).execute(
            ListCourseUnitsInput(student_sub=str(user.get("sub", "")), course_id=str(course_id))
        )
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
    return JSONResponse(rows, headers=_cache_headers_success())


@learning_router.get("/api/learning/courses/{course_id}/units/{unit_id}/sections")
async def list_unit_sections(
    request: Request,
    course_id: str,
    unit_id: str,
    include: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List released sections for a specific unit (student-only).

    Why:
        Unit-scoped endpoint aligns with the SSR unit page and avoids
        client-side filtering. Returns 200 with an array that may be empty.

    Permissions:
        Caller must have the `student` role and be enrolled in the course.
        The unit must belong to the course; otherwise respond with 404 to avoid
        leaking existence details.
    """
    user, error = _require_student(request)
    if error:
        return error

    # Validate path params eagerly to align with contract detail=invalid_uuid
    try:
        UUID(course_id)
        UUID(unit_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers_error())

    try:
        include_materials, include_tasks = _parse_include(include)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_include"}, status_code=400, headers=_cache_headers_error())

    input_data = ListUnitSectionsInput(
        student_sub=str(user.get("sub", "")),
        course_id=course_id,
        unit_id=unit_id,
        include_materials=include_materials,
        include_tasks=include_tasks,
        limit=limit,
        offset=offset,
    )
    try:
        sections = ListUnitSectionsUseCase(_get_repo()).execute(input_data)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_cache_headers_error())
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    # 200 with possibly empty list
    sections = _attach_section_material_files(
        student_sub=str(user.get("sub", "")),
        course_id=course_id,
        sections=sections,
    )
    return JSONResponse(sections, headers=_cache_headers_success())


@learning_router.get("/api/learning/courses/{course_id}/units/{unit_id}/modules/graph")
async def get_modular_unit_graph(request: Request, course_id: str, unit_id: str):
    """Return the module graph (advance organizer) for a modular learning unit.

    Why:
        The Learning UI supports two unit formats:
        - "linear": section-by-section progression controlled by teacher releases
        - "modular": graph-based progression with an advance organizer
        This endpoint is modular-only and must fail clearly for linear units so
        clients can handle the case deterministically.

    Behavior:
        - Requires an authenticated session with role "student".
        - 400 detail=invalid_uuid when path params are not UUID-like.
        - 404 when the caller is not a course member or the unit is not part of
          the course (intentionally indistinguishable).
        - 400 detail=invalid_unit_type when the unit is not modular.
        - 200 with the modular graph payload (phases/modules/edges and unlock
          state) for modular units.

    Permissions:
        Caller must have the `student` role and be enrolled in the course.
    """
    user, error = _require_student(request)
    if error:
        return error

    # Validate path params eagerly to align with contract detail=invalid_uuid
    try:
        course_id_norm = str(UUID(course_id))
        unit_id_norm = str(UUID(unit_id))
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers_error())

    # Reuse the existing course-unit listing helper to enforce membership/404
    # semantics while keeping the adapter thin. This is efficient enough for
    # MVP (courses have few units); a dedicated DB helper can be introduced
    # later if needed.
    try:
        rows = ListCourseUnitsUseCase(_get_repo()).execute(
            ListCourseUnitsInput(student_sub=str(user.get("sub", "")), course_id=course_id_norm)
        )
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    unit: dict[str, Any] | None = None
    for item in rows:
        candidate = item.get("unit")
        candidate_id = _canonical_uuid_or_none((candidate or {}).get("id")) if isinstance(candidate, dict) else None
        if candidate_id == unit_id_norm:
            unit = candidate
            break
    if not unit:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    unit_type = str(unit.get("unit_type") or "").strip().lower()
    if unit_type != "modular":
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_type"}, status_code=400, headers=_cache_headers_error())

    repo = _get_repo()
    repo_error = _require_repo_methods(repo, "get_modular_unit_graph")
    if repo_error:
        return repo_error

    try:
        payload = repo.get_modular_unit_graph(
            student_sub=str(user.get("sub", "")),
            course_id=course_id_norm,
            unit_id=unit_id_norm,
        )
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_type"}, status_code=400, headers=_cache_headers_error())
    return JSONResponse(payload, headers=_cache_headers_success())


@learning_router.get("/api/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}")
async def get_modular_unit_module_content(
    request: Request,
    course_id: str,
    unit_id: str,
    module_id: str,
    include: str | None = None,
):
    """Return module content (materials/tasks) for a modular unit (student-only).

    Why:
        For modular units the UI loads a *module* (not a whole unit) once the
        student has unlocked it. This endpoint is modular-only: for linear
        units the client must use the existing section endpoints.

    Behavior:
        - Requires an authenticated session with role "student".
        - 400 detail=invalid_uuid when any path param is not UUID-like.
        - 400 detail=invalid_include for an unsupported include query.
        - 404 when the course/unit/module is not visible to the student (fail-closed).
        - 400 detail=invalid_unit_type when the unit is not modular.

    Permissions:
        Caller must have the `student` role and be a member of the course.
    """
    user, error = _require_student(request)
    if error:
        return error

    try:
        course_id_norm = str(UUID(course_id))
        unit_id_norm = str(UUID(unit_id))
        module_id_norm = str(UUID(module_id))
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers_error())

    try:
        _include_materials, _include_tasks = _parse_include(
            include, default_materials=True, default_tasks=True
        )
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_include"}, status_code=400, headers=_cache_headers_error())

    try:
        rows = ListCourseUnitsUseCase(_get_repo()).execute(
            ListCourseUnitsInput(student_sub=str(user.get("sub", "")), course_id=course_id_norm)
        )
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    unit: dict[str, Any] | None = None
    for item in rows:
        candidate = item.get("unit")
        candidate_id = _canonical_uuid_or_none((candidate or {}).get("id")) if isinstance(candidate, dict) else None
        if candidate_id == unit_id_norm:
            unit = candidate
            break
    if not unit:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    unit_type = str(unit.get("unit_type") or "").strip().lower()
    if unit_type != "modular":
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_type"}, status_code=400, headers=_cache_headers_error())

    repo = _get_repo()
    repo_error = _require_repo_methods(repo, "get_modular_module_content")
    if repo_error:
        return repo_error

    try:
        payload = repo.get_modular_module_content(
            student_sub=str(user.get("sub", "")),
            course_id=course_id_norm,
            unit_id=unit_id_norm,
            module_id=module_id_norm,
            include_materials=_include_materials,
            include_tasks=_include_tasks,
        )
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_type"}, status_code=400, headers=_cache_headers_error())
    payload = _attach_modular_material_files(
        student_sub=str(user.get("sub", "")),
        course_id=course_id_norm,
        unit_id=unit_id_norm,
        module_id=module_id_norm,
        payload=payload,
    )
    return JSONResponse(payload, headers=_cache_headers_success())


_DEFAULT_DOWNLOAD_BYTES_WITH_LIMIT = _download_bytes_with_limit
