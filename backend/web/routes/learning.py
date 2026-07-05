"""Learning (Lernen) API routes."""

from __future__ import annotations

import base64
import json
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
from backend.learning.submission_kind_policy import validate_task_submission_kind
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
    CreateSubmissionInput,
    CreateSubmissionUseCase,
    FinalizeLatestDraftInput,
    FinalizeLatestDraftUseCase,
    ListSubmissionsInput,
    ListSubmissionsUseCase,
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
    ALLOWED_FILE_MIME,
    ALLOWED_IMAGE_MIME,
    STORAGE_KEY_RE,
    resolve_local_verify_root_from_env,
    verification_config_from_env,
)
from backend.storage.verification import verify_storage_object_integrity
from backend.storage.config import get_submissions_bucket, get_learning_max_upload_bytes, get_materials_max_upload_bytes
from backend.storage.keys import make_submission_key
from backend.storage.submission_content_signatures import validate_submission_content_signature
from backend.storage.upload_intents import normalize_upload_intent_headers
from backend.storage.mime_types import FILIUS_FLS_MIME, JPEG_MIME, MAKECODE_HEX_MIME, PDF_MIME, PNG_MIME, SCRATCH_SB3_MIME
from backend.web.material_file_access import (
    MaterialVisibilityLookupUnavailable,
    StudentMaterialFileMetadata,
    load_student_material_file_metadata,
    load_student_material_file_metadata_batch,
)
from backend.web.routes import learning_downloads
import httpx
from urllib.parse import urlparse as _urlparse, quote as _quote
learning_router = APIRouter(tags=["Learning"])
logger = logging.getLogger("gustav.web.learning")

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


def _attach_submission_files(submission: dict[str, Any], *, course_id: str, task_id: str) -> dict[str, Any]:
    """Attach short-lived artifact URLs for learner-visible submission history.

    Why:
        The learner history workspace should be able to preview or reopen
        earlier upload submissions without exposing raw storage keys in the UI.
        We therefore decorate API payloads with a tiny `files[]` view model.

    Security:
        URLs are short-lived signed download URLs from the configured storage
        adapter. When no adapter is available, we fail closed and expose an
        empty list.
    """

    payload = dict(submission or {})
    payload["files"] = []

    kind = str(payload.get("kind") or "").strip().lower()
    storage_key = str(payload.get("storage_key") or "").strip()
    mime_type = str(payload.get("mime_type") or "").strip().lower()
    size_bytes = payload.get("size_bytes")
    if kind not in {"image", "file"} or not storage_key or not mime_type:
        return payload

    try:
        size_int = int(size_bytes)
    except (TypeError, ValueError):
        return payload
    if size_int <= 0:
        return payload

    submission_id = str(payload.get("id") or "").strip()
    if not (_is_uuid_like(submission_id) and _is_uuid_like(course_id) and _is_uuid_like(task_id)):
        return payload

    url = _submission_file_href(course_id=course_id, task_id=task_id, submission_id=submission_id, disposition="inline")
    download_url = _submission_file_href(
        course_id=course_id,
        task_id=task_id,
        submission_id=submission_id,
        disposition="attachment",
    )

    payload["files"] = [
        {
            "mime": mime_type,
            "size": size_int,
            "url": url,
            "download_url": download_url,
        }
    ]
    return payload


def _submission_file_href(*, course_id: str, task_id: str, submission_id: str, disposition: str) -> str:
    """Return a stable same-origin file URL for a learner submission."""

    return (
        f"/api/learning/courses/{_quote(str(course_id), safe='')}/tasks/{_quote(str(task_id), safe='')}"
        f"/submissions/{_quote(str(submission_id), safe='')}/file?disposition={_quote(str(disposition), safe='')}"
    )


def _material_file_href(*, course_id: str, material_id: str, disposition: str) -> str:
    """Return a stable same-origin file URL for a learner-visible material."""

    return (
        f"/api/learning/courses/{_quote(str(course_id), safe='')}/materials/"
        f"{_quote(str(material_id), safe='')}/file?disposition={_quote(str(disposition), safe='')}"
    )


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


def _upload_intent_ttl_seconds() -> int:
    raw = (os.getenv("LEARNING_UPLOAD_INTENT_TTL_SECONDS") or "").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 600
    return max(60, min(value, 24 * 60 * 60))


def _dev_upload_stub_enabled() -> bool:
    return (os.getenv("ENABLE_DEV_UPLOAD_STUB", "false") or "").strip().lower() == "true"


def _upload_proxy_enabled() -> bool:
    return (os.getenv("ENABLE_STORAGE_UPLOAD_PROXY", "false") or "").strip().lower() == "true"


def _upload_proxy_timeout_seconds() -> float:
    raw = (os.getenv("LEARNING_UPLOAD_PROXY_TIMEOUT_SECONDS") or "").strip()
    try:
        value = float(raw)
    except ValueError:
        value = 30.0
    return max(5.0, min(value, 120.0))


def _encode_proxy_headers(headers: Any) -> str | None:
    """Return a base64url-encoded JSON payload containing presign headers."""
    if not headers:
        return None
    try:
        mapping = dict(headers)
    except Exception:
        return None
    safe: dict[str, str] = {}
    for key, value in mapping.items():
        if key is None or value is None:
            continue
        k = str(key).strip()
        if not k:
            continue
        safe[k] = str(value)
    if not safe:
        return None
    raw = json.dumps(safe, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_proxy_headers(token: str | None) -> dict[str, str]:
    if not token:
        return {}
    try:
        padded = token + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        parsed = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}
    safe: dict[str, str] = {}
    for key, value in parsed.items():
        if isinstance(key, str) and isinstance(value, str):
            safe[key] = value
    return safe


def _filter_upload_proxy_headers(headers: dict[str, str]) -> dict[str, str]:
    """Return a safe allowlist of headers for the internal upload proxy.

    Why:
        The upload-proxy forwards request bytes to a presigned Storage URL.
        Presign headers must be treated as untrusted input (even if typically
        generated by our backend) and must not allow forwarding of sensitive
        hop-by-hop headers like `Authorization`, `Cookie`, or `Host`.

    Behavior:
        - Keeps only headers required for Supabase Storage presigned uploads.
        - Comparison is case-insensitive but preserves original key casing.
    """

    allowed = {"content-type", "x-upsert"}
    out: dict[str, str] = {}
    for key, value in (headers or {}).items():
        lk = str(key).strip().lower()
        if not lk or lk not in allowed:
            continue
        out[str(key)] = str(value)
    return out


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


def _normalized_parts(parsed) -> tuple[str, str, int | None]:  # type: ignore[override]
    scheme = (getattr(parsed, "scheme", "") or "").lower()
    host = (getattr(parsed, "hostname", "") or "").lower()
    port = getattr(parsed, "port", None)
    if port is None:
        if scheme == "https":
            port = 443
        elif scheme == "http":
            port = 80
    return scheme, host, port


async def _async_forward_upload(
    *,
    url: str,
    payload: bytes,
    content_type: str,
    timeout: float,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Forward the upload to Supabase (patchable for tests)."""
    send_headers: dict[str, str] = {}
    if headers:
        for key, value in headers.items():
            if key is None or value is None:
                continue
            send_headers[str(key)] = str(value)
    if not any(str(k).lower() == "content-type" for k in send_headers):
        send_headers["Content-Type"] = content_type
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.put(url, content=payload, headers=send_headers)


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


def _resolve_student_material_file_url(
    *,
    student_sub: str,
    course_id: str,
    material_id: str,
) -> str | None:
    if not (student_sub and _is_uuid_like(course_id) and _is_uuid_like(material_id)):
        return None
    repo = _get_repo()
    try:
        metadata = load_student_material_file_metadata(
            repo=repo,
            student_sub=student_sub,
            course_id=str(course_id),
            material_id=str(material_id),
        )
    except Exception:
        return None
    if metadata is None:
        return None
    return _material_file_href(course_id=course_id, material_id=material_id, disposition="inline")


def _load_visible_material_file_metadata(
    *,
    student_sub: str,
    course_id: str,
    material_ids: list[str],
) -> dict[str, StudentMaterialFileMetadata]:
    """Load visible file-material metadata for a student with one DB connection."""

    valid_material_ids = [str(material_id) for material_id in material_ids if _is_uuid_like(material_id)]
    if not (student_sub and _is_uuid_like(course_id) and valid_material_ids):
        return {}

    repo = _get_repo()
    try:
        return load_student_material_file_metadata_batch(
            repo=repo,
            student_sub=student_sub,
            course_id=str(course_id),
            material_ids=valid_material_ids,
        )
    except Exception:
        return {}


def _resolve_student_modular_material_file_url(
    *,
    student_sub: str,
    course_id: str,
    material_id: str,
) -> str | None:
    return _resolve_student_material_file_url(
        student_sub=student_sub,
        course_id=course_id,
        material_id=material_id,
    )


def _attach_section_material_files(
    *,
    student_sub: str,
    course_id: str,
    sections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    material_ids = [
        str(material.get("id") or "")
        for section in sections
        for material in (section.get("materials") or [])
        if isinstance(section, dict) and isinstance(material, dict) and material.get("kind") == "file"
    ]
    material_rows = _load_visible_material_file_metadata(
        student_sub=student_sub,
        course_id=course_id,
        material_ids=material_ids,
    )
    enriched: list[dict[str, Any]] = []
    for section in sections:
        payload = dict(section)
        materials = []
        for material in payload.get("materials") or []:
            material_payload = dict(material)
            if material_payload.get("kind") == "file":
                material_id = str(material_payload.get("id") or "")
                material_payload["file_url"] = (
                    _material_file_href(course_id=course_id, material_id=material_id, disposition="inline")
                    if material_id in material_rows
                    else None
                )
            else:
                material_payload["file_url"] = None
            materials.append(material_payload)
        payload["materials"] = materials
        enriched.append(payload)
    return enriched


def _attach_modular_material_files(
    *,
    student_sub: str,
    course_id: str,
    unit_id: str,
    module_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    out = dict(payload)
    material_rows = _load_visible_material_file_metadata(
        student_sub=student_sub,
        course_id=course_id,
        material_ids=[
            str(material.get("id") or "")
            for material in (out.get("materials") or [])
            if isinstance(material, dict) and material.get("kind") == "file"
        ],
    )
    materials = []
    for material in out.get("materials") or []:
        material_payload = dict(material)
        if material_payload.get("kind") == "file":
            material_id = str(material_payload.get("id") or "")
            material_payload["file_url"] = (
                _material_file_href(course_id=course_id, material_id=material_id, disposition="inline")
                if material_id in material_rows
                else None
            )
        else:
            material_payload["file_url"] = None
        materials.append(material_payload)
    out["materials"] = materials
    return out


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


def _validate_submission_payload(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Validate and normalize the submission payload (text/image/file/h5p).

    Why:
        Keep FastAPI layer thin, but ensure inputs are sane before invoking
        use cases/repo and touching the database. Enforces MIME allowlists,
        size bounds, and storage key/sha256 formats. Error detail strings match
        the OpenAPI contract for precise client handling.

    Returns:
        (kind, clean_payload) where kind in {text,image,file,h5p} and
        clean_payload contains the normalized fields for the given kind.

    Errors:
        Raises ValueError with one of: 'invalid_input', 'invalid_image_payload',
        'invalid_file_payload', 'invalid_h5p_payload'.
    """
    if not isinstance(payload, dict):
        raise ValueError("invalid_input")
    intent_raw = payload.get("intent")
    if intent_raw is None:
        intent = "submit"
    elif not isinstance(intent_raw, str):
        raise ValueError("invalid_input")
    else:
        intent = intent_raw.strip().lower()
    if intent not in {"feedback", "submit"}:
        raise ValueError("invalid_input")
    kind = payload.get("kind")
    if kind not in ("text", "image", "file", "h5p"):
        raise ValueError("invalid_input")
    if kind == "text":
        text_body = payload.get("text_body")
        if not isinstance(text_body, str) or not text_body.strip():
            # Harmonize with API contract: return generic invalid_input
            raise ValueError("invalid_input")
        # Optional guardrail: prevent oversized payloads from overloading DB
        # Global limit: allow up to 64k characters for text submissions.
        if len(text_body) > 65_536:
            raise ValueError("invalid_input")
        return kind, {"intent": intent, "text_body": text_body.strip()}
    elif kind == "h5p":
        required = {"score_raw", "score_max"}
        if not required.issubset(payload.keys()):
            raise ValueError("invalid_h5p_payload")
        try:
            raw_int = int(payload.get("score_raw"))
            max_int = int(payload.get("score_max"))
        except (TypeError, ValueError):
            raise ValueError("invalid_h5p_payload") from None
        if raw_int < 0 or max_int < 0 or raw_int > max_int:
            raise ValueError("invalid_h5p_payload")
        return kind, {"intent": intent, "score_raw": raw_int, "score_max": max_int}
    elif kind == "image":
        # Image submissions require finalized storage metadata
        required = {"storage_key", "mime_type", "size_bytes", "sha256"}
        if not required.issubset(payload.keys()):
            raise ValueError("invalid_image_payload")
        size_bytes = payload.get("size_bytes")
        try:
            size_int = int(size_bytes)
        except (TypeError, ValueError):
            raise ValueError("invalid_image_payload") from None
        if size_int <= 0 or size_int > _max_upload_bytes():
            raise ValueError("invalid_image_payload")
        mime_type_raw = payload.get("mime_type")
        if not isinstance(mime_type_raw, str) or not mime_type_raw:
            raise ValueError("invalid_image_payload")
        # Compare MIME types case-insensitively; normalize for downstream checks.
        mime_type = mime_type_raw.strip().lower()
        if mime_type not in ALLOWED_IMAGE_MIME:
            raise ValueError("invalid_image_payload")
        storage_key = payload.get("storage_key")
        if not isinstance(storage_key, str) or not storage_key:
            raise ValueError("invalid_image_payload")
        # Restrict to path-like storage keys (defense-in-depth):
        # - allow only lower-case, digits, _, ., /, -
        # - first char must be [a-z0-9]
        # - explicitly forbid any ".." sequence to avoid traversal-like patterns
        if not STORAGE_KEY_RE.fullmatch(storage_key):
            raise ValueError("invalid_image_payload")
        sha256 = payload.get("sha256")
        if not isinstance(sha256, str):
            raise ValueError("invalid_image_payload")
        sha256_normalized = sha256.strip().lower()
        if len(sha256_normalized) != 64 or any(c not in "0123456789abcdef" for c in sha256_normalized):
            raise ValueError("invalid_image_payload")
        return kind, {
            "intent": intent,
            "storage_key": storage_key,
            "mime_type": mime_type,
            "size_bytes": size_int,
            "sha256": sha256_normalized,
        }
    else:  # kind == "file"
        # PDF submissions (MVP) with finalized storage metadata
        required = {"storage_key", "mime_type", "size_bytes", "sha256"}
        if not required.issubset(payload.keys()):
            raise ValueError("invalid_file_payload")
        size_bytes = payload.get("size_bytes")
        try:
            size_int = int(size_bytes)
        except (TypeError, ValueError):
            raise ValueError("invalid_file_payload") from None
        if size_int <= 0 or size_int > _max_upload_bytes():
            raise ValueError("invalid_file_payload")
        mime_type_raw = payload.get("mime_type")
        if not isinstance(mime_type_raw, str) or not mime_type_raw:
            raise ValueError("invalid_file_payload")
        # Compare MIME types case-insensitively; normalize for downstream checks.
        mime_type = mime_type_raw.strip().lower()
        if mime_type not in ALLOWED_FILE_MIME:
            raise ValueError("invalid_file_payload")
        storage_key = payload.get("storage_key")
        if not isinstance(storage_key, str) or not storage_key:
            raise ValueError("invalid_file_payload")
        if not STORAGE_KEY_RE.fullmatch(storage_key):
            raise ValueError("invalid_file_payload")
        sha256 = payload.get("sha256")
        if not isinstance(sha256, str):
            raise ValueError("invalid_file_payload")
        sha256_normalized = sha256.strip().lower()
        if len(sha256_normalized) != 64 or any(c not in "0123456789abcdef" for c in sha256_normalized):
            raise ValueError("invalid_file_payload")
        return kind, {
            "intent": intent,
            "storage_key": storage_key,
            "mime_type": mime_type,
            "size_bytes": size_int,
            "sha256": sha256_normalized,
        }


@learning_router.post("/api/learning/courses/{course_id}/tasks/{task_id}/submissions")
async def create_submission(request: Request, course_id: str, task_id: str, payload: dict[str, Any]):
    """Create a student submission for a task.

    Security:
        Enforces same-origin using Origin or Referer; rejects cross-site POSTs.

    Permissions:
        Caller must be an enrolled student with access to the released task.
    """
    # CSRF defense: Always require Origin/Referer presence and same-origin.
    # Unified policy (dev = prod): no fallback to non-strict mode.
    if not _require_strict_same_origin(request):
        return JSONResponse({"error": "forbidden", "detail": "csrf_violation"}, status_code=403, headers=_cache_headers_error())

    # Authorization (student-only) after CSRF: prevents masking CSRF diagnostics
    # with unrelated authorization errors.
    user, error = _require_student(request)
    if error:
        return error

    try:
        UUID(course_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers_error())
    try:
        UUID(task_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers_error())

    idempotency_key = request.headers.get("Idempotency-Key")
    # Contract: Idempotency-Key must be ≤ 64 characters when provided
    if idempotency_key is not None and len(idempotency_key) > 64:
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_input"},
            status_code=400,
            headers=_cache_headers_error(),
        )
    if idempotency_key is not None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", idempotency_key):
            return JSONResponse(
                {"error": "bad_request", "detail": "invalid_input"},
                status_code=400,
                headers=_cache_headers_error(),
            )

    try:
        kind, clean_payload = _validate_submission_payload(payload)
    except ValueError as exc:
        detail = str(exc) if str(exc) else "invalid_input"
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400, headers=_cache_headers_error())

    # Optional storage integrity verification for image/PDF submissions.
    # Enabled when STORAGE_VERIFY_ROOT is set; can be enforced with
    # REQUIRE_STORAGE_VERIFY=true. Protects against mismatched size/hash.
    if kind in ("image", "file"):
        storage_key = clean_payload.get("storage_key")
        sha256 = clean_payload.get("sha256")
        size_bytes = clean_payload.get("size_bytes")
        mime_type = clean_payload.get("mime_type")
        try:
            ok, _reason = _verify_storage_object(
                str(storage_key), str(sha256), int(size_bytes), str(mime_type)
            )
        except Exception:
            ok = False
        if not ok:
            detail = "invalid_image_payload" if kind == "image" else "invalid_file_payload"
            return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400, headers=_cache_headers_error())

    validation_bytes: bytes | None = None
    task_kind_for_submission = "native"
    task_kind_for_submission_normalized = "native"
    if kind in ("image", "file"):
        repo = _get_repo()
        task_kind_reader = getattr(repo, "get_task_kind_for_student", None)
        if callable(task_kind_reader):
            try:
                task_kind_for_submission = str(
                    task_kind_reader(
                        student_sub=str(user.get("sub", "")),
                        course_id=str(course_id),
                        task_id=str(task_id),
                    )
                )
            except PermissionError:
                return JSONResponse({"error": "forbidden"}, status_code=403, headers=_cache_headers_error())
            except LookupError:
                return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
            except Exception:
                return JSONResponse(
                    {"error": "service_unavailable", "detail": "submission_validation_unavailable"},
                    status_code=503,
                    headers=_cache_headers_error(),
                )
        task_kind_for_submission_normalized = str(task_kind_for_submission or "native").strip().lower()
        try:
            validate_task_submission_kind(
                task_kind=task_kind_for_submission_normalized,
                submission_kind=kind,
                mime_type=str(clean_payload.get("mime_type") or ""),
            )
        except ValueError as exc:
            return JSONResponse(
                {"error": "bad_request", "detail": str(exc) or "invalid_input"},
                status_code=400,
                headers=_cache_headers_error(),
            )
        storage_key = str(clean_payload.get("storage_key") or "")
        mime_type = str(clean_payload.get("mime_type") or "")
        validation_bytes = await _load_storage_bytes_for_validation(storage_key=storage_key, max_bytes=_max_upload_bytes())
        if not validation_bytes:
            return JSONResponse(
                {"error": "service_unavailable", "detail": "submission_validation_unavailable"},
                status_code=503,
                headers=_cache_headers_error(),
            )
        try:
            validate_submission_content_signature(mime_type, validation_bytes)
        except ValueError:
            logger.info(
                "learning_upload_content_signature_mismatch",
                extra={
                    "reason": "invalid_upload_content",
                    "mime_type": str(mime_type).strip().lower(),
                    "task_kind": task_kind_for_submission_normalized,
                    "byte_count": len(validation_bytes),
                },
            )
            return JSONResponse(
                {"error": "bad_request", "detail": "invalid_upload_content"},
                status_code=400,
                headers=_cache_headers_error(),
            )

    # Scratch `.sb3` validation (fail early with stable detail codes).
    if kind == "file" and str(clean_payload.get("mime_type") or "").strip().lower() == SCRATCH_SB3_MIME:
        if task_kind_for_submission_normalized == "scratch":
            sb3_bytes = validation_bytes
            if not sb3_bytes:
                return JSONResponse(
                    {"error": "service_unavailable", "detail": "sb3_validation_unavailable"},
                    status_code=503,
                    headers=_cache_headers_error(),
                )
            from backend.storage.sb3_validation import SB3ValidationError, load_project_json

            try:
                _ = load_project_json(sb3_bytes)
            except SB3ValidationError as exc:
                return JSONResponse(
                    {"error": "bad_request", "detail": str(exc.code)},
                    status_code=400,
                    headers=_cache_headers_error(),
                )

    # MakeCode `.hex` validation for Calliope tasks.
    if kind == "file" and str(clean_payload.get("mime_type") or "").strip().lower() == MAKECODE_HEX_MIME:
        if task_kind_for_submission_normalized == "calliope":
            hex_bytes = validation_bytes
            if not hex_bytes:
                return JSONResponse(
                    {"error": "service_unavailable", "detail": "hex_validation_unavailable"},
                    status_code=503,
                    headers=_cache_headers_error(),
                )
            from backend.storage.makecode_hex_validation import MakeCodeHexValidationError, extract_makecode_project_from_hex

            try:
                _ = extract_makecode_project_from_hex(hex_bytes)
            except MakeCodeHexValidationError as exc:
                if str(exc.code) in {"invalid_hex_file", "missing_makecode_source"}:
                    logger.info(
                        "calliope_hex_soft_extraction_error",
                        extra={"detail": str(exc.code), "course_id": str(course_id), "task_id": str(task_id)},
                    )
                else:
                    return JSONResponse(
                        {"error": "bad_request", "detail": str(exc.code)},
                        status_code=400,
                        headers=_cache_headers_error(),
                    )

    # Filius `.fls` validation for Filius tasks (fail early with stable detail codes).
    if kind == "file" and str(clean_payload.get("mime_type") or "").strip().lower() == FILIUS_FLS_MIME:
        if task_kind_for_submission_normalized != "filius":
            return JSONResponse(
                {"error": "bad_request", "detail": "invalid_file_payload"},
                status_code=400,
                headers=_cache_headers_error(),
            )

        fls_bytes = validation_bytes
        if not fls_bytes:
            return JSONResponse(
                {"error": "service_unavailable", "detail": "filius_validation_unavailable"},
                status_code=503,
                headers=_cache_headers_error(),
            )
        from backend.storage.filius_validation import FiliusValidationError, extract_configuration_xml_bytes

        try:
            _ = extract_configuration_xml_bytes(fls_bytes)
        except FiliusValidationError as exc:
            return JSONResponse(
                {"error": "bad_request", "detail": str(exc.code)},
                status_code=400,
                headers=_cache_headers_error(),
            )

    submission_input = CreateSubmissionInput(
        course_id=course_id,
        task_id=task_id,
        student_sub=str(user.get("sub", "")),
        intent=str(clean_payload.get("intent") or "submit"),
        kind=kind,
        text_body=clean_payload.get("text_body"),
        storage_key=clean_payload.get("storage_key"),
        mime_type=clean_payload.get("mime_type"),
        size_bytes=clean_payload.get("size_bytes"),
        sha256=clean_payload.get("sha256"),
        score_raw=clean_payload.get("score_raw"),
        score_max=clean_payload.get("score_max"),
        idempotency_key=idempotency_key,
    )

    try:
        submission = CreateSubmissionUseCase(_get_repo()).execute(submission_input)
    except PermissionError:
        # Permission-denied at the use case layer (e.g., not enrolled or task
        # not released). Attach a diagnostic header to distinguish from CSRF.
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
            diag = f"reason=permission,env={_environment_for_request(request)},origin={origin_hdr},server={server_origin}"
        except Exception:
            diag = "reason=permission,env=?,origin=?,server=?"
        try:
            log_path = (os.getenv("CSRF_DIAG_LOG") or "").strip()
            if log_path:
                with open(log_path, "a", encoding="utf-8") as fp:
                    fp.write(f"create_submission: {diag}\n")
        except Exception:
            pass
        # Do not leak diagnostics to clients; log above when CSRF_DIAG_LOG set.
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_cache_headers_error())
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400, headers=_cache_headers_error())
    except Exception:
        # Fail closed: when persistence is unavailable, do not pretend success.
        return JSONResponse(
            {"error": "service_unavailable", "detail": "submission_persistence_unavailable"},
            status_code=503,
            headers=_cache_headers_error(),
        )

    # Opportunistic dev processing for PDF submissions (synchronous, MVP):
    # In dev environments where a local validation root exists, attempt to
    # read the uploaded PDF bytes directly and kick off the rendering pipeline.
    # This is best-effort and must not block or affect the API response.
    try:
        if kind == "file" and str(clean_payload.get("mime_type")) == PDF_MIME:
            root = resolve_local_verify_root_from_env() or ""
            env = _environment_for_request(request)
            prod_like = env in {"prod", "production", "stage", "staging"}
            if root and (not prod_like):
                _dev_try_process_pdf(
                    root=root,
                    storage_key=str(clean_payload.get("storage_key") or ""),
                    submission_id=str(submission.get("id")),
                    course_id=str(course_id),
                    task_id=str(task_id),
                    student_sub=str(user.get("sub", "")),
                )
    except Exception:
        pass

    # Response semantics:
    # - H5P submissions are persisted synchronously (score only) → 201 Created.
    # - Other kinds enter the async pipeline → 202 Accepted.
    status_code = 201 if kind == "h5p" else 202
    return JSONResponse(submission, status_code=status_code, headers=_cache_headers_success())


@learning_router.post("/api/learning/courses/{course_id}/tasks/{task_id}/submissions/finalize")
async def finalize_submission(request: Request, course_id: str, task_id: str, payload: dict[str, Any] | None = None):
    """Create a final submission from the latest completed feedback draft."""
    if not _require_strict_same_origin(request):
        return JSONResponse({"error": "forbidden", "detail": "csrf_violation"}, status_code=403, headers=_cache_headers_error())

    user, auth_error = _require_student(request)
    if auth_error:
        return auth_error

    try:
        UUID(course_id)
        UUID(task_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers_error())

    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key is not None and len(idempotency_key) > 64:
        return JSONResponse({"error": "bad_request", "detail": "invalid_input"}, status_code=400, headers=_cache_headers_error())
    if idempotency_key is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", idempotency_key):
        return JSONResponse({"error": "bad_request", "detail": "invalid_input"}, status_code=400, headers=_cache_headers_error())

    finalize_input = FinalizeLatestDraftInput(
        course_id=course_id,
        task_id=task_id,
        student_sub=str(user.get("sub", "")),
        idempotency_key=idempotency_key,
    )

    try:
        submission = FinalizeLatestDraftUseCase(_get_repo()).execute(finalize_input)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_cache_headers_error())
    except LookupError as exc:
        detail = str(exc) or "not_found"
        if detail == "draft_missing":
            return JSONResponse({"error": "conflict", "detail": detail}, status_code=409, headers=_cache_headers_error())
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
    except RuntimeError as exc:
        return JSONResponse({"error": "conflict", "detail": str(exc) or "draft_not_ready"}, status_code=409, headers=_cache_headers_error())
    except ValueError as exc:
        return JSONResponse({"error": "bad_request", "detail": str(exc) or "invalid_input"}, status_code=400, headers=_cache_headers_error())
    except Exception:
        return JSONResponse(
            {"error": "service_unavailable", "detail": "submission_persistence_unavailable"},
            status_code=503,
            headers=_cache_headers_error(),
        )

    decorated = _attach_submission_files(submission, course_id=course_id, task_id=task_id)
    return JSONResponse(decorated, status_code=201, headers=_cache_headers_success())


def _dev_try_process_pdf(*, root: str, storage_key: str, submission_id: str, course_id: str, task_id: str, student_sub: str) -> None:
    """Best-effort dev helper: render, persist pages, and mark extracted.

    Intent:
        In lokalen Umgebungen, in denen Uploads auf das Dateisystem geschrieben
        werden, verarbeiten wir eingereichte PDFs sofort und speichern
        abgeleitete Seitenbilder unter einem stabilen Pfad.

    Permissions:
        Nur für Dev. Produktion soll einen Worker/Queue nutzen.
    """
    from pathlib import Path as _Path
    base = _Path(root).resolve()
    pdf_path = (base / storage_key).resolve()
    common = os.path.commonpath([str(base), str(pdf_path)])
    if common != str(base) or not pdf_path.exists() or not pdf_path.is_file():
        return

    try:
        data = pdf_path.read_bytes()
    except Exception:
        return

    # Lazy import optional deps only when invoked
    try:
        from backend.vision.pipeline import process_pdf_bytes  # type: ignore
        from backend.vision.persistence import SubmissionScope, persist_rendered_pages  # type: ignore
    except Exception:
        return

    try:
        pages, _meta = process_pdf_bytes(data)
    except Exception:
        return

    # Minimal filesystem-backed BinaryWriteStorage implementation for dev
    class _FSWriter:
        def __init__(self, root_dir: _Path) -> None:
            self._root = root_dir

        def put_object(self, *, bucket: str, key: str, body: bytes, content_type: str) -> None:  # noqa: D401
            # Ignore content_type; write bytes under root/bucket/key
            target = (self._root / bucket / key).resolve()
            # Enforce containment in root
            common2 = os.path.commonpath([str(self._root), str(target)])
            if common2 != str(self._root):
                raise RuntimeError("path_escape_blocked")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)

    fs = _FSWriter(base)
    scope = SubmissionScope(
        course_id=str(course_id), task_id=str(task_id), student_sub=str(student_sub), submission_id=str(submission_id)
    )
    try:
        persist_rendered_pages(
            storage=fs,
            bucket=_storage_bucket(),
            scope=scope,
            pages=pages,
            repo=_get_repo(),  # type: ignore[arg-type]
        )
    except Exception:
        # Never let dev persistence affect the request path
        return


@learning_router.post("/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents")
async def create_upload_intent(request: Request, course_id: str, task_id: str, payload: dict[str, Any]):
    """Create a short-lived upload intent for a submission asset (image/PDF/SB3).

    Why:
        Client-side uploads avoid sending large binaries through our API server.
        We return a presigned target (stub in dev) and storage_key metadata;
        the client PUTs the file there, then submits the finalized metadata via
        the standard submissions endpoint.

    Parameters:
        request: FastAPI request with the caller's session.
        course_id: UUID string of the course context (path).
        task_id: UUID string of the task (path).
        payload: JSON object with keys:
            - kind: "image" | "file" (PDF or Scratch SB3, depending on Task.kind)
            - filename: original filename for intent construction
            - mime_type: declared content-type (validated against allowlist)
            - size_bytes: integer size of the upload in bytes (≤ 10 MiB)

    Returns:
        200 JSON with fields: intent_id, storage_key, url, headers,
        accepted_mime_types, max_size_bytes, expires_at. Clients must still
        finish by POSTing to /submissions with storage metadata and sha256.

    Security:
        Same-origin required. Caller must have role "student". In the MVP,
        membership/visibility checks are enforced when creating the submission
        (defense at the DB boundary, RLS). We may move guards earlier later.
    """
    user = _current_user(request)
    if not user:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_cache_headers_error())
    roles = user.get("roles") or []
    if not isinstance(roles, list) or "student" not in roles:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
    # Strict CSRF for browser-triggered POSTs: require Origin/Referer presence
    # and same-origin (server-to-server calls should not use this endpoint).
    if not _require_strict_same_origin(request):
        return JSONResponse(
            {"error": "forbidden", "detail": "csrf_violation"},
            status_code=403,
            headers=_cache_headers_error(),
        )

    # Basic path validation
    try:
        UUID(course_id)
        UUID(task_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers_error())

    # Input validation
    if not isinstance(payload, dict):
        return JSONResponse({"error": "bad_request", "detail": "invalid_input"}, status_code=400, headers=_cache_headers_error())
    kind = payload.get("kind")
    filename = str(payload.get("filename") or "").strip()
    # Compare MIME types case-insensitively; normalize for downstream policy checks.
    mime_type = str(payload.get("mime_type") or "").strip().lower()
    size_bytes = payload.get("size_bytes")
    try:
        size_int = int(size_bytes)
    except Exception:
        return JSONResponse({"error": "bad_request", "detail": "invalid_input"}, status_code=400, headers=_cache_headers_error())
    if not filename or len(filename) > 255:
        return JSONResponse({"error": "bad_request", "detail": "invalid_input"}, status_code=400, headers=_cache_headers_error())
    if size_int <= 0 or size_int > _max_upload_bytes():
        return JSONResponse({"error": "bad_request", "detail": "size_exceeded"}, status_code=400, headers=_cache_headers_error())
    if kind not in {"image", "file"}:
        return JSONResponse({"error": "bad_request", "detail": "invalid_input"}, status_code=400, headers=_cache_headers_error())

    # Authorization/visibility: ensure the caller is a member and the task is visible.
    # We use the existing submissions read-path as an access check; the repo enforces
    # membership and released visibility (RLS + helpers in the DB implementation).
    try:
        _ = ListSubmissionsUseCase(_get_repo()).execute(
            ListSubmissionsInput(
                course_id=str(course_id),
                task_id=str(task_id),
                student_sub=str(user.get("sub", "")),
                limit=1,
                offset=0,
            )
        )
    except PermissionError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
    except LookupError:
        # Task not visible (or course/unit mismatch) should not leak existence
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
    except Exception:
        # Fail closed: without a reliable authorization check we must not hand out
        # a presigned upload capability.
        return JSONResponse(
            {"error": "service_unavailable", "detail": "authorization_unavailable"},
            status_code=503,
            headers=_cache_headers_error(),
        )

    # Optional: fetch Task.kind for stricter per-task allowlists (e.g., Scratch is SB3-only).
    task_kind = "native"
    repo = _get_repo()
    if callable(getattr(repo, "get_task_kind_for_student", None)):
        try:
            task_kind = str(
                repo.get_task_kind_for_student(
                    student_sub=str(user.get("sub", "")),
                    course_id=str(course_id),
                    task_id=str(task_id),
                )
            )
        except PermissionError:
            return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
        except LookupError:
            return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
        except Exception:
            return JSONResponse(
                {"error": "service_unavailable", "detail": "authorization_unavailable"},
                status_code=503,
                headers=_cache_headers_error(),
            )

    task_kind = (task_kind or "native").strip().lower()
    if task_kind == "scratch":
        # Scratch is SB3-only (upload-only). We do not accept images/PDF here.
        if kind != "file":
            return JSONResponse({"error": "bad_request", "detail": "mime_not_allowed"}, status_code=400, headers=_cache_headers_error())
        if mime_type != SCRATCH_SB3_MIME:
            return JSONResponse({"error": "bad_request", "detail": "mime_not_allowed"}, status_code=400, headers=_cache_headers_error())
        accepted = [SCRATCH_SB3_MIME]
    elif task_kind == "calliope":
        # Calliope MakeCode tasks are HEX-only (upload-only). We do not accept images/PDF here.
        if kind != "file":
            return JSONResponse({"error": "bad_request", "detail": "mime_not_allowed"}, status_code=400, headers=_cache_headers_error())
        if mime_type != MAKECODE_HEX_MIME:
            return JSONResponse({"error": "bad_request", "detail": "mime_not_allowed"}, status_code=400, headers=_cache_headers_error())
        accepted = [MAKECODE_HEX_MIME]
    elif task_kind == "filius":
        # Filius tasks are FLS-only (upload-only). We do not accept images/PDF here.
        if kind != "file":
            return JSONResponse({"error": "bad_request", "detail": "mime_not_allowed"}, status_code=400, headers=_cache_headers_error())
        if mime_type != FILIUS_FLS_MIME:
            return JSONResponse({"error": "bad_request", "detail": "mime_not_allowed"}, status_code=400, headers=_cache_headers_error())
        accepted = [FILIUS_FLS_MIME]
    else:
        if kind == "image":
            if mime_type not in ALLOWED_IMAGE_MIME:
                return JSONResponse(
                    {"error": "bad_request", "detail": "mime_not_allowed"}, status_code=400, headers=_cache_headers_error()
                )
            accepted = sorted(list(ALLOWED_IMAGE_MIME))
        else:  # kind == "file"
            # Non-scratch tasks accept only PDFs in MVP.
            if mime_type != PDF_MIME:
                return JSONResponse({"error": "bad_request", "detail": "mime_not_allowed"}, status_code=400, headers=_cache_headers_error())
            accepted = [PDF_MIME]

    # Build a storage key (lowercase path, no traversal) — the value is later
    # validated again at submission time with a strict regex.
    import time as _time
    from uuid import uuid4 as _uuid4
    student_sub = str(user.get("sub", "student")).lower()
    ts = int(_time.time() * 1000)
    if mime_type == PNG_MIME:
        ext = ".png"
    elif mime_type == JPEG_MIME:
        ext = ".jpg"
    elif mime_type == SCRATCH_SB3_MIME:
        ext = ".sb3"
    elif mime_type == MAKECODE_HEX_MIME:
        ext = ".hex"
    elif mime_type == FILIUS_FLS_MIME:
        ext = ".fls"
    else:
        ext = ".pdf"
    storage_key = make_submission_key(
        course_id=str(course_id),
        task_id=str(task_id),
        student_sub=str(student_sub),
        ext=ext,
        epoch_ms=ts,
        uuid_hex=_uuid4().hex,
    )

    bucket = _storage_bucket()
    adapter = _current_storage_adapter()
    # Lazy wiring: if adapter is not ready, try wiring once now.
    if isinstance(adapter, NullStorageAdapter):
        try:
            _wire_storage()
        except Exception:
            # Non-fatal; fall through to stub/503 handling.
            pass
        adapter = _current_storage_adapter()  # refresh after potential wiring

    # Dev fallback when adapter remains unavailable.
    if not bucket or isinstance(adapter, NullStorageAdapter):
        if _dev_upload_stub_enabled():
            presign_url = f"/api/learning/internal/upload-stub?storage_key={_quote(storage_key)}"
            from datetime import datetime, timezone, timedelta
            intent = {
                "intent_id": str(_uuid4()),
                "storage_key": storage_key,
                "url": presign_url,
                "headers": normalize_upload_intent_headers({}, fallback_content_type=mime_type),
                "accepted_mime_types": accepted,
                "max_size_bytes": _max_upload_bytes(),
                "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=_upload_intent_ttl_seconds())).isoformat(timespec="seconds"),
            }
            return JSONResponse(intent, status_code=200, headers=_cache_headers_success())
        return JSONResponse(
            {"error": "service_unavailable", "detail": "storage_adapter_not_configured"},
            status_code=503,
            headers=_cache_headers_error(),
        )

    ttl_seconds = _upload_intent_ttl_seconds()
    upload_headers = {"Content-Type": mime_type}
    try:
        presigned = adapter.presign_upload(
            bucket=bucket,
            key=storage_key,
            expires_in=ttl_seconds,
            headers=upload_headers,
        )
    except RuntimeError as exc:
        if str(exc) == "storage_adapter_not_configured":
            return JSONResponse(
                {"error": "service_unavailable", "detail": "storage_adapter_not_configured"},
                status_code=503,
                headers=_cache_headers_error(),
            )
        raise

    presign_url = presigned.get("url")
    if not presign_url:
        return JSONResponse(
            {"error": "service_unavailable", "detail": "presign_failed"},
            status_code=503,
            headers=_cache_headers_error(),
        )

    from datetime import datetime, timezone, timedelta
    url_out = str(presign_url)
    # Apply same-origin proxy when enabled and the presign target host matches
    # our configured SUPABASE_URL host. This keeps behavior stable for fakes
    # in tests and avoids coupling to a specific adapter class name.
    try:
        headers_src: dict[str, Any] = dict(presigned.get("headers") or upload_headers)
    except Exception:
        headers_src = dict(upload_headers)
    proxy_headers_token = _encode_proxy_headers(headers_src)

    if _upload_proxy_enabled():
        base = (os.getenv("SUPABASE_URL") or "").strip()
        try:
            parsed_target = _urlparse(str(presign_url))
            parsed_base = _urlparse(base)
            th = parsed_target.hostname or ""
            bh = parsed_base.hostname or ""
        except Exception:
            th = bh = ""
        if th and bh and th == bh:
            # Same-origin proxy to avoid Storage CORS; target url is passed as query
            url_out = f"/api/learning/internal/upload-proxy?url={_quote(str(presign_url))}"
            if proxy_headers_token:
                url_out += f"&headers={_quote(proxy_headers_token)}"
    headers_out = normalize_upload_intent_headers(headers_src, fallback_content_type=mime_type)
    intent = {
        "intent_id": str(_uuid4()),
        "storage_key": storage_key,
        "url": url_out,
        "headers": headers_out,
        "accepted_mime_types": accepted,
        "max_size_bytes": _max_upload_bytes(),
        # Short-lived expiry (defense-in-depth): 10 minutes from now (UTC)
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat(timespec="seconds"),
    }
    return JSONResponse(intent, status_code=200, headers=_cache_headers_success())


def _verify_storage_object(storage_key: str, sha256: str, size_bytes: int, mime_type: str) -> tuple[bool, str]:
    """
    Validate that the referenced storage object matches the submission metadata.

    Why:
        Student submissions are finalised asynchronously; before accepting the
        payload we must ensure that the object uploaded to Supabase (or the dev
        stub directory) matches the declared checksum/size to prevent tampering.
    Parameters:
        storage_key: Relative object key within the learning bucket.
        sha256: Hex-encoded checksum provided by the client after upload.
        size_bytes: Expected object size from the upload intent.
        mime_type: MIME recorded alongside the submission (not used here, passed
            for future policy hooks).
    Behavior:
        Delegates to the shared verification helper which first attempts a
        `HEAD` request via the configured storage adapter and, if allowed,
        falls back to local filesystem verification. Returns (ok, reason).
    Permissions:
        Only callable from the authenticated backend flow; the caller must have
        already ensured the student is authorised for the submission.
    """

    config = verification_config_from_env()
    return verify_storage_object_integrity(
        adapter=_current_storage_adapter(),
        storage_key=storage_key,
        expected_sha256=sha256,
        expected_size=size_bytes,
        mime_type=mime_type,
        config=config,
    )


def _load_local_storage_bytes_for_validation(*, root: str, storage_key: str, max_bytes: int) -> bytes | None:
    """Read a local file beneath STORAGE_VERIFY_ROOT with path containment checks."""
    if not root or not storage_key:
        return None
    try:
        from pathlib import Path

        base = Path(root).resolve()
        target = (base / storage_key).resolve()
        common = os.path.commonpath([str(base), str(target)])
    except Exception:
        return None
    if common != str(base) or (not target.exists()) or (not target.is_file()):
        return None
    try:
        size = int(target.stat().st_size)
    except Exception:
        return None
    if size <= 0 or size > int(max_bytes):
        return None
    try:
        return target.read_bytes()
    except Exception:
        return None


async def _download_bytes_with_limit(*, url: str, max_bytes: int, headers: dict[str, str] | None = None) -> bytes | None:
    """Download bytes from a presigned URL with a hard cap (no redirects)."""

    return await learning_downloads.download_bytes_with_limit(
        url=url,
        max_bytes=max_bytes,
        headers=headers,
        environment=_current_environment(),
    )


_DEFAULT_DOWNLOAD_BYTES_WITH_LIMIT = _download_bytes_with_limit


async def _load_storage_bytes_for_validation(*, storage_key: str, max_bytes: int) -> bytes | None:
    """Fetch bytes for validation either from local verify root or via presigned download."""
    root = resolve_local_verify_root_from_env() or ""
    local = _load_local_storage_bytes_for_validation(root=root, storage_key=storage_key, max_bytes=max_bytes)
    if local is not None:
        return local

    bucket = _storage_bucket()
    adapter = _current_storage_adapter()
    if not bucket or isinstance(adapter, NullStorageAdapter):
        return None
    try:
        presigned = adapter.presign_download(bucket=bucket, key=storage_key, expires_in=60, disposition="inline")
    except Exception:
        return None
    url = str((presigned or {}).get("url") or "").strip()
    headers = presigned.get("headers") if isinstance(presigned, dict) else None
    try:
        hdrs = {str(k): str(v) for k, v in dict(headers or {}).items() if k and v}
    except Exception:
        hdrs = None
    return await _download_bytes_with_limit(url=url, max_bytes=max_bytes, headers=hdrs)


@learning_router.put("/api/learning/internal/upload-stub")
async def internal_upload_stub(request: Request):
    """Accept a small file upload and persist under STORAGE_VERIFY_ROOT.

    Why:
        In dev/offline setups we don't have a presigned upload target. This
        stub endpoint allows the browser to PUT the file directly to the app,
        writing to a local directory for integrity verification.

    Behavior:
        - Requires same-origin (Origin/Referer) and an authenticated student.
        - Query string must include `storage_key` (path-like; validated).
        - Body bytes are written to STORAGE_VERIFY_ROOT/storage_key (or `./.tmp/dev_uploads/...` when unset).
        - Responds with JSON: {sha256, size_bytes}.
    """
    if not _dev_upload_stub_enabled():
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
    user, error = _require_student(request)
    if error:
        return error
    if not _require_strict_same_origin(request):
        return JSONResponse({"error": "forbidden", "detail": "csrf_violation"}, status_code=403, headers=_cache_headers_error())

    storage_key = str(request.query_params.get("storage_key") or "").strip()
    if not storage_key or not STORAGE_KEY_RE.fullmatch(storage_key):
        return JSONResponse({"error": "bad_request", "detail": "invalid_storage_key"}, status_code=400, headers=_cache_headers_error())

    # Resolve target path safely beneath the configured local validation root.
    root = resolve_local_verify_root_from_env()
    if not root:
        return JSONResponse(
            {"error": "service_unavailable", "detail": "upload_stub_storage_unavailable"},
            status_code=503,
            headers=_cache_headers_error(),
        )
    from pathlib import Path as _Path
    base = _Path(root).resolve()
    target = (base / storage_key).resolve()
    try:
        common = os.path.commonpath([str(base), str(target)])
    except Exception:
        return JSONResponse({"error": "bad_request", "detail": "path_error"}, status_code=400, headers=_cache_headers_error())
    if common != str(base):
        return JSONResponse({"error": "bad_request", "detail": "path_escape"}, status_code=400, headers=_cache_headers_error())

    body, body_error = await _read_request_stream_with_limit(request, _max_upload_bytes())
    if body_error:
        return JSONResponse({"error": "bad_request", "detail": body_error}, status_code=400, headers=_cache_headers_error())

    # Ensure parent dirs exist and write the file.
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as fh:
        fh.write(body)

    # Compute sha256 for the response so the client can finalize submission.
    import hashlib as _hashlib
    h = _hashlib.sha256()
    h.update(body)
    sha_hex = h.hexdigest()
    return JSONResponse({"sha256": sha_hex, "size_bytes": len(body)}, status_code=200, headers=_cache_headers_success())


@learning_router.put("/api/learning/internal/upload-proxy")
async def internal_upload_proxy(request: Request):
    """Proxy a file upload to a presigned Storage URL (same-origin fallback).

    Security:
        - Requires authenticated student and strict same-origin.
        - Validates the target URL host against SUPABASE_URL to prevent SSRF.
        - Allows http only for local dev hosts (localhost, 127.0.0.0/8, ::1, host.docker.internal).
        - Restricts the path to `/storage/v1/object/...` to narrow SSRF surface.
        - Enforces MAX_UPLOAD_BYTES size and a MIME allowlist (images/PDF and
          `application/octet-stream` for compatibility with some browsers).
    Behavior:
        - Forwards the raw body with the incoming Content-Type header.
        - Returns {sha256, size_bytes} on success (200≤code<300).
    """
    target_host_for_log = "n/a"
    content_type_for_log = request.headers.get("content-type") or "application/octet-stream"

    def _proxy_error(payload: dict[str, str], *, status_code: int, reason: str) -> JSONResponse:
        _current_emit_upload_proxy_telemetry()(
            outcome="error",
            status_code=status_code,
            reason=reason,
            target_host=target_host_for_log,
            content_type=content_type_for_log,
            size_bytes=None,
        )
        return JSONResponse(payload, status_code=status_code, headers=_cache_headers_error())

    user, error = _require_student(request)
    if error:
        _current_emit_upload_proxy_telemetry()(
            outcome="error",
            status_code=int(getattr(error, "status_code", 401)),
            reason="auth",
            target_host=target_host_for_log,
            content_type=content_type_for_log,
            size_bytes=None,
        )
        return error
    if not _require_strict_same_origin(request):
        return _proxy_error({"error": "forbidden", "detail": "csrf_violation"}, status_code=403, reason="csrf_violation")
    if not _upload_proxy_enabled():
        return _proxy_error({"error": "not_found"}, status_code=404, reason="feature_disabled")

    target = str(request.query_params.get("url") or "").strip()
    header_token = str(request.query_params.get("headers") or "").strip()
    forward_headers = _filter_upload_proxy_headers(_decode_proxy_headers(header_token))
    if not target:
        return _proxy_error({"error": "bad_request", "detail": "missing_url"}, status_code=400, reason="missing_url")
    base = (os.getenv("SUPABASE_URL") or "").strip()
    public_base = (os.getenv("SUPABASE_PUBLIC_URL") or "").strip()
    try:
        parsed_target = _urlparse(target)
        parsed_base = _urlparse(base) if base else None
        parsed_public = _urlparse(public_base) if public_base else None
    except Exception:
        return _proxy_error({"error": "bad_request", "detail": "invalid_url"}, status_code=400, reason="invalid_url_parse")

    target_scheme, target_host, target_port = _normalized_parts(parsed_target)
    target_host_for_log = target_host or "n/a"

    if not target_scheme or target_scheme not in {"http", "https"} or not target_host:
        return _proxy_error({"error": "bad_request", "detail": "invalid_url"}, status_code=400, reason="invalid_url_parts")

    local_hosts = {"localhost", "::1", "host.docker.internal"}
    is_local_http = target_host in local_hosts or target_host.startswith("127.")
    if target_scheme == "http" and not is_local_http:
        return _proxy_error({"error": "bad_request", "detail": "invalid_url"}, status_code=400, reason="invalid_url_scheme")
    allowed_hosts: list[tuple[str, str, int | None]] = []
    for parsed in (parsed_base, parsed_public):
        if not parsed:
            continue
        scheme, host, port = _normalized_parts(parsed)
        if host:
            allowed_hosts.append((scheme, host, port))
    if not allowed_hosts:
        return _proxy_error({"error": "bad_request", "detail": "invalid_url_host"}, status_code=400, reason="missing_allowed_hosts")

    matched_scheme = None
    matched_port: int | None = None
    for scheme, host, port in allowed_hosts:
        if target_host == host:
            matched_scheme = scheme
            matched_port = port
            break

    if matched_scheme is None:
        return _proxy_error({"error": "bad_request", "detail": "invalid_url_host"}, status_code=400, reason="invalid_url_host")
    if matched_scheme == "https" and target_scheme != "https":
        return _proxy_error({"error": "bad_request", "detail": "invalid_url"}, status_code=400, reason="invalid_url_scheme")
    if matched_port and target_port and target_port != matched_port:
        return _proxy_error({"error": "bad_request", "detail": "invalid_url_host"}, status_code=400, reason="invalid_url_port")

    # Enforce that the path targets the storage upload endpoint to reduce SSRF surface.
    path = parsed_target.path or "/"
    # Be tolerant to accidental double slashes from upstream clients by
    # collapsing them before applying prefix checks (dev/local presigners can
    # produce .../storage/v1//object/...). This does not weaken the check
    # because we still require the fixed upload prefix afterwards.
    while "//" in path:
        path = path.replace("//", "/")
    if ".." in path or re.search(r"%2e", path, flags=re.IGNORECASE):
        return _proxy_error({"error": "bad_request", "detail": "invalid_url"}, status_code=400, reason="invalid_url_path")
    if not path.startswith("/storage/v1/object/"):
        return _proxy_error({"error": "bad_request", "detail": "invalid_url"}, status_code=400, reason="invalid_url_path")

    body, body_error = await _read_request_stream_with_limit(request, _max_upload_bytes())
    if body_error:
        return _proxy_error({"error": "bad_request", "detail": body_error}, status_code=400, reason=body_error)
    content_type = request.headers.get("content-type") or "application/octet-stream"
    content_type_for_log = content_type
    # Enforce MIME allowlist for uploads proxied through our origin.
    allowed_mime = (set(ALLOWED_IMAGE_MIME) | set(ALLOWED_FILE_MIME) | {"application/octet-stream"})
    if content_type not in allowed_mime:
        return _proxy_error({"error": "bad_request", "detail": "mime_not_allowed"}, status_code=400, reason="mime_not_allowed")

    try:
        resp = await _current_async_forward_upload()(
            url=target,
            payload=body,
            content_type=content_type,
            timeout=_upload_proxy_timeout_seconds(),
            headers=forward_headers or None,
        )
    except Exception:
        # Prod-parity: any upstream exception is a 502 (no soft-200 in dev/test).
        return _proxy_error({"error": "bad_gateway", "detail": "proxy_failed"}, status_code=502, reason="proxy_failed")
    if getattr(resp, "status_code", 500) >= 300:
        # Prod-parity: non-2xx upstream is a 502 in all environments.
        return _proxy_error({"error": "bad_gateway", "detail": "upstream_error"}, status_code=502, reason="upstream_error")

    import hashlib as _hashlib
    h = _hashlib.sha256(); h.update(body)
    _current_emit_upload_proxy_telemetry()(
        outcome="success",
        status_code=200,
        reason="ok",
        target_host=target_host_for_log,
        content_type=content_type_for_log,
        size_bytes=len(body),
    )
    return JSONResponse({"sha256": h.hexdigest(), "size_bytes": len(body)}, status_code=200, headers=_cache_headers_success())

@learning_router.get("/api/learning/courses/{course_id}/tasks/{task_id}/submissions")
async def list_submissions(
    request: Request,
    course_id: str,
    task_id: str,
    limit: int = 20,
    offset: int = 0,
):
    """Return the caller's submission history for a task (student-only).

    Pagination:
        `limit` is clamped to 1..100 and `offset` to >= 0 by the use case.
    """
    user, error = _require_student(request)
    if error:
        return error

    try:
        UUID(course_id)
        UUID(task_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers_error())

    input_data = ListSubmissionsInput(
        course_id=course_id,
        task_id=task_id,
        student_sub=str(user.get("sub", "")),
        limit=limit,
        offset=offset,
    )

    try:
        submissions = ListSubmissionsUseCase(_get_repo()).execute(input_data)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_cache_headers_error())
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    decorated = [
        _attach_submission_files(submission, course_id=course_id, task_id=task_id)
        for submission in submissions
    ]
    return JSONResponse(decorated, status_code=200, headers=_cache_headers_success())


def _normalize_download_disposition(raw: str | None, *, default: str = "inline") -> str | None:
    disposition = (raw or default).strip().lower()
    if disposition not in {"inline", "attachment"}:
        return None
    return disposition


@learning_router.get("/api/learning/courses/{course_id}/tasks/{task_id}/submissions/{submission_id}/file")
async def get_submission_file(
    request: Request,
    course_id: str,
    task_id: str,
    submission_id: str,
    disposition: str | None = None,
):
    """Stream a learner-visible submission file through a stable same-origin route."""

    user, error = _require_student(request)
    if error:
        return error

    normalized_disposition = _normalize_download_disposition(disposition)
    if normalized_disposition is None:
        return JSONResponse({"error": "bad_request", "detail": "invalid_disposition"}, status_code=400, headers=_cache_headers_error())

    try:
        UUID(course_id)
        UUID(task_id)
        UUID(submission_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers_error())

    try:
        submissions = ListSubmissionsUseCase(_get_repo()).execute(
            ListSubmissionsInput(
                course_id=course_id,
                task_id=task_id,
                student_sub=str(user.get("sub", "")),
                limit=100,
                offset=0,
            )
        )
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_cache_headers_error())
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    submission = next((item for item in submissions if str(item.get("id") or "") == submission_id), None)
    if not isinstance(submission, dict):
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    storage_key = str(submission.get("storage_key") or "").strip()
    mime_type = str(submission.get("mime_type") or "").strip().lower()
    kind = str(submission.get("kind") or "").strip().lower()
    try:
        size_bytes = max(0, int(submission.get("size_bytes") or 0))
    except (TypeError, ValueError):
        size_bytes = 0
    if kind not in {"image", "file"} or not storage_key or not mime_type:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    body = await _download_storage_object_via_presign(
        bucket=_storage_bucket(),
        key=storage_key,
        disposition=normalized_disposition,
        max_bytes=max(_max_upload_bytes(), size_bytes),
    )
    if body is None:
        return JSONResponse({"error": "service_unavailable"}, status_code=503, headers=_cache_headers_error())

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


@learning_router.get("/api/learning/courses/{course_id}/materials/{material_id}/file")
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
        return JSONResponse({"error": "bad_request", "detail": "invalid_disposition"}, status_code=400, headers=_cache_headers_error())

    try:
        UUID(course_id)
        UUID(material_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers_error())

    repo = _get_repo()
    try:
        metadata = load_student_material_file_metadata(
            repo=repo,
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
    filename = _safe_download_filename(metadata.filename_original or os.path.basename(storage_key), "material.bin")
    size_bytes = int(metadata.size_bytes or 0)
    if not storage_key or not mime_type:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    body = await _download_storage_object_via_presign(
        bucket=(__import__("backend.teaching.services.materials", fromlist=["MaterialFileSettings"]).MaterialFileSettings().storage_bucket),
        key=storage_key,
        disposition=normalized_disposition,
        max_bytes=max(get_materials_max_upload_bytes(), size_bytes),
        adapter=_teaching_storage_adapter(),
    )
    if body is None:
        return JSONResponse({"error": "service_unavailable"}, status_code=503, headers=_cache_headers_error())

    return Response(
        content=body,
        media_type=mime_type or "application/octet-stream",
        headers={
            "Cache-Control": "private, no-store",
            "Vary": "Origin",
            "Content-Disposition": f'{normalized_disposition}; filename="{filename}"',
        },
    )


@learning_router.get("/api/learning/courses/{course_id}/sections/{section_id}/materials/{material_id}/file")
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
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers_error())

    user, error = _require_student(request)
    if error:
        return error

    repo = _get_repo()
    try:
        metadata = load_student_material_file_metadata(
            repo=repo,
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
