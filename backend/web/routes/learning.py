"""Learning (Lernen) API routes."""

from __future__ import annotations

import sys

# Ensure imports via `routes.learning` and `backend.web.routes.learning` point to the same module.
if __name__ == "backend.web.routes.learning":
    sys.modules.setdefault("routes.learning", sys.modules[__name__])
elif __name__ == "routes.learning":
    sys.modules.setdefault("backend.web.routes.learning", sys.modules[__name__])

import base64
import json
import logging
import os
import re
import sys as _sys
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
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
from teaching.storage import NullStorageAdapter, StorageAdapterProtocol  # type: ignore
try:
    from backend.web.storage_wiring import wire_supabase_adapter_if_configured as _wire_storage  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - container fallback when package path is flattened
    from storage_wiring import wire_supabase_adapter_if_configured as _wire_storage  # type: ignore
from backend.storage.learning_policy import (
    ALLOWED_FILE_MIME,
    ALLOWED_IMAGE_MIME,
    STORAGE_KEY_RE,
    verification_config_from_env,
)
from backend.storage.verification import verify_storage_object_integrity
from backend.storage.config import get_submissions_bucket, get_learning_max_upload_bytes
from backend.storage.keys import make_submission_key
from backend.storage.sb3_validation import SCRATCH_SB3_MIME
from backend.storage.makecode_hex_validation import MAKECODE_HEX_MIME
import httpx
from urllib.parse import urlparse as _urlparse, quote as _quote
import psycopg


learning_router = APIRouter(tags=["Learning"])
logger = logging.getLogger("gustav.web.learning")

STORAGE_ADAPTER: StorageAdapterProtocol = NullStorageAdapter()


def set_storage_adapter(adapter: StorageAdapterProtocol) -> None:
    """Allow tests or startup code to provide a concrete storage adapter."""
    global STORAGE_ADAPTER
    STORAGE_ADAPTER = adapter


def _storage_bucket() -> str:
    # Delegate to centralized config to avoid drift and simplify testing.
    return get_submissions_bucket()


def _max_upload_bytes() -> int:
    return get_learning_max_upload_bytes()


def _attach_submission_files(submission: dict[str, Any]) -> dict[str, Any]:
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

    bucket = _storage_bucket()
    adapter = STORAGE_ADAPTER
    if not bucket or isinstance(adapter, NullStorageAdapter):
        return payload

    try:
        presigned = adapter.presign_download(
            bucket=bucket,
            key=storage_key,
            expires_in=60,
            disposition="inline",
        )
    except Exception:
        return payload

    url = str((presigned or {}).get("url") or "").strip()
    if not url:
        return payload

    payload["files"] = [
        {
            "mime": mime_type,
            "size": size_int,
            "url": url,
        }
    ]
    return payload


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
    try:
        import routes.teaching as teaching_routes  # type: ignore
        return getattr(teaching_routes, "STORAGE_ADAPTER", None)
    except Exception:
        return None


def _resolve_student_material_file_url(
    *,
    student_sub: str,
    course_id: str,
    section_id: str,
    material_id: str,
) -> str | None:
    material_urls = _load_released_section_material_urls(
        student_sub=student_sub,
        course_id=course_id,
        section_material_pairs=[(section_id, material_id)],
    )
    return material_urls.get(str(material_id))


def _presign_material_url(*, adapter: object, storage_key: str) -> str | None:
    """Return a short-lived preview URL for a material storage key."""

    if not storage_key or not hasattr(adapter, "presign_download"):
        return None

    try:
        from teaching.services.materials import MaterialFileSettings  # type: ignore

        settings = MaterialFileSettings()
        presign = adapter.presign_download(
            bucket=settings.storage_bucket,
            key=storage_key,
            expires_in=settings.download_url_ttl_seconds,
            disposition="inline",
        )
        url = presign.get("url") if isinstance(presign, dict) else None
        return str(url).strip() if isinstance(url, str) and url.strip() else None
    except Exception:
        return None


def _load_released_section_material_urls(
    *,
    student_sub: str,
    course_id: str,
    section_material_pairs: list[tuple[str, str]],
) -> dict[str, str | None]:
    """Load released section-material URLs with one DB connection."""

    valid_pairs = [
        (str(section_id), str(material_id))
        for section_id, material_id in section_material_pairs
        if _is_uuid_like(section_id) and _is_uuid_like(material_id)
    ]
    if not (student_sub and _is_uuid_like(course_id) and valid_pairs):
        return {}

    repo = _get_repo()
    dsn = str(getattr(repo, "_dsn", "") or "").strip()
    adapter = _teaching_storage_adapter()
    if not dsn or adapter is None or not hasattr(adapter, "presign_download"):
        return {}

    try:
        section_ids = [section_id for section_id, _ in valid_pairs]
        material_ids = [material_id for _, material_id in valid_pairs]
        storage_keys: dict[str, str] = {}
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                set_current_sub = getattr(repo, "_set_current_sub", None)
                if callable(set_current_sub):
                    set_current_sub(cur, student_sub)
                else:
                    cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
                cur.execute(
                    """
                    with requested(section_id, material_id) as (
                        select * from unnest(%s::uuid[], %s::uuid[])
                    )
                    select requested.material_id::text, released.storage_key
                      from requested
                      join lateral public.get_released_materials_for_student(%s, %s::uuid, requested.section_id) released
                        on released.id = requested.material_id
                    """,
                    (section_ids, material_ids, student_sub, str(course_id)),
                )
                for material_id, storage_key in cur.fetchall() or []:
                    if isinstance(material_id, str) and isinstance(storage_key, str) and storage_key.strip():
                        storage_keys[material_id] = storage_key.strip()
        return {
            material_id: _presign_material_url(adapter=adapter, storage_key=storage_key)
            for material_id, storage_key in storage_keys.items()
        }
    except Exception:
        return {}


def _load_modular_material_urls(
    *,
    student_sub: str,
    course_id: str,
    unit_id: str,
    module_id: str,
    material_ids: list[str],
) -> dict[str, str | None]:
    """Load modular material URLs with one DB connection."""

    valid_material_ids = [str(material_id) for material_id in material_ids if _is_uuid_like(material_id)]
    if not (
        student_sub
        and _is_uuid_like(course_id)
        and _is_uuid_like(unit_id)
        and _is_uuid_like(module_id)
        and valid_material_ids
    ):
        return {}

    repo = _get_repo()
    dsn = str(getattr(repo, "_dsn", "") or "").strip()
    adapter = _teaching_storage_adapter()
    if not dsn or adapter is None or not hasattr(adapter, "presign_download"):
        return {}

    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                set_current_sub = getattr(repo, "_set_current_sub", None)
                if callable(set_current_sub):
                    set_current_sub(cur, student_sub)
                else:
                    cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
                set_current_course_id = getattr(repo, "_set_current_course_id", None)
                if callable(set_current_course_id):
                    set_current_course_id(cur, str(course_id))
                else:
                    cur.execute("select set_config('app.current_course_id', %s, true)", (str(course_id),))

                cur.execute(
                    """
                    select exists(
                             select 1
                               from public.course_memberships
                              where course_id = %s::uuid
                                and student_id = %s
                         )
                    """,
                    (str(course_id), student_sub),
                )
                if not bool((cur.fetchone() or [False])[0]):
                    return {}

                cur.execute(
                    """
                    select exists(
                             select 1
                               from public.course_modules
                              where course_id = %s::uuid
                                and unit_id = %s::uuid
                         )
                    """,
                    (str(course_id), str(unit_id)),
                )
                if not bool((cur.fetchone() or [False])[0]):
                    return {}

                cur.execute(
                    """
                    select section_id::text
                      from public.unit_modules
                     where id = %s::uuid
                       and unit_id = %s::uuid
                     limit 1
                    """,
                    (str(module_id), str(unit_id)),
                )
                section_row = cur.fetchone()
                section_id = section_row[0] if section_row and isinstance(section_row[0], str) and section_row[0].strip() else None
                if not section_id:
                    return {}

                cur.execute(
                    "select public.modular_section_is_open_or_done_for_student(%s, %s::uuid, %s::uuid, %s::uuid)",
                    (student_sub, str(course_id), str(unit_id), str(section_id)),
                )
                if not bool((cur.fetchone() or [False])[0]):
                    return {}

                cur.execute(
                    """
                    select id::text, storage_key
                      from public.unit_materials
                     where id = any(%s::uuid[])
                       and section_id = %s::uuid
                       and kind = 'file'
                     order by position asc
                    """,
                    (valid_material_ids, str(section_id)),
                )
                storage_keys = {
                    str(material_id): str(storage_key).strip()
                    for material_id, storage_key in cur.fetchall() or []
                    if isinstance(material_id, str) and isinstance(storage_key, str) and storage_key.strip()
                }
        return {
            material_id: _presign_material_url(adapter=adapter, storage_key=storage_key)
            for material_id, storage_key in storage_keys.items()
        }
    except Exception:
        return {}


def _resolve_student_modular_material_file_url(
    *,
    student_sub: str,
    course_id: str,
    unit_id: str,
    module_id: str,
    material_id: str,
) -> str | None:
    material_urls = _load_modular_material_urls(
        student_sub=student_sub,
        course_id=course_id,
        unit_id=unit_id,
        module_id=module_id,
        material_ids=[material_id],
    )
    return material_urls.get(str(material_id))


def _attach_section_material_files(
    *,
    student_sub: str,
    course_id: str,
    sections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    section_material_pairs = [
        (str((section.get("section") or {}).get("id") or ""), str(material.get("id") or ""))
        for section in sections
        for material in (section.get("materials") or [])
        if isinstance(section, dict) and isinstance(material, dict) and material.get("kind") == "file"
    ]
    material_urls = _load_released_section_material_urls(
        student_sub=student_sub,
        course_id=course_id,
        section_material_pairs=section_material_pairs,
    )
    enriched: list[dict[str, Any]] = []
    for section in sections:
        payload = dict(section)
        materials = []
        for material in payload.get("materials") or []:
            material_payload = dict(material)
            if material_payload.get("kind") == "file":
                material_payload["file_url"] = material_urls.get(str(material_payload.get("id") or ""))
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
    material_urls = _load_modular_material_urls(
        student_sub=student_sub,
        course_id=course_id,
        unit_id=unit_id,
        module_id=module_id,
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
            material_payload["file_url"] = material_urls.get(str(material_payload.get("id") or ""))
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
    - Try to import `backend.web.main` or `main` and read `SETTINGS.environment`.
    - Fallback to `GUSTAV_ENV` (default "dev").
    """
    def _read_env_from_module(mod: object | None) -> str | None:
        if mod is None:
            return None
        try:
            settings = getattr(mod, "SETTINGS", None)
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
        mod = sys.modules.get(alias)
        if mod is None:
            return None
        try:
            settings = getattr(mod, "SETTINGS", None)
        except Exception:
            return None
        if settings is None:
            return None
        # Only short-circuit when an explicit override is present so tests can
        # observe module-level overrides even if later imports fail.
        if getattr(settings, "_env_override", None) is None:
            return None
        return _read_env_from_module(mod)

    for alias in ("backend.web.main", "main"):
        env = _loaded_override_env(alias)
        if env:
            return env

    import importlib

    for alias in ("backend.web.main", "main"):
        try:
            mod = importlib.import_module(alias)
        except Exception:
            continue
        env = _read_env_from_module(mod)
        if env:
            return env
    return (os.getenv("GUSTAV_ENV", "dev") or "").lower()


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
    # Keep the public alias in sync for tests that do `isinstance(routes.learning.REPO, ...)`.
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
            ok, reason = _verify_storage_object(str(storage_key), str(sha256), int(size_bytes), str(mime_type))
        except Exception:
            ok, reason = (False, "verification_error")
        if not ok:
            detail = "invalid_image_payload" if kind == "image" else "invalid_file_payload"
            return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400, headers=_cache_headers_error())

    # Scratch `.sb3` validation (fail early with stable detail codes).
    if kind == "file" and str(clean_payload.get("mime_type") or "").strip().lower() == SCRATCH_SB3_MIME:
        task_kind = "native"
        repo = _get_repo()
        task_kind_reader = getattr(repo, "get_task_kind_for_student", None)
        if callable(task_kind_reader):
            try:
                task_kind = str(
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

        if str(task_kind or "").strip().lower() == "scratch":
            storage_key = str(clean_payload.get("storage_key") or "")
            sb3_bytes = await _load_storage_bytes_for_validation(storage_key=storage_key, max_bytes=_max_upload_bytes())
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

    # MakeCode `.hex` validation for Calliope tasks (fail early with stable detail codes).
    if kind == "file" and str(clean_payload.get("mime_type") or "").strip().lower() == MAKECODE_HEX_MIME:
        task_kind = "native"
        repo = _get_repo()
        task_kind_reader = getattr(repo, "get_task_kind_for_student", None)
        if callable(task_kind_reader):
            try:
                task_kind = str(
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

        if str(task_kind or "").strip().lower() == "calliope":
            storage_key = str(clean_payload.get("storage_key") or "")
            hex_bytes = await _load_storage_bytes_for_validation(storage_key=storage_key, max_bytes=_max_upload_bytes())
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
            diag = f"reason=permission,env={_current_environment()},origin={origin_hdr},server={server_origin}"
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
    # In dev environments where STORAGE_VERIFY_ROOT is configured, attempt to
    # read the uploaded PDF bytes directly and kick off the rendering pipeline.
    # This is best-effort and must not block or affect the API response.
    try:
        if kind == "file" and str(clean_payload.get("mime_type")) == "application/pdf":
            root = (os.getenv("STORAGE_VERIFY_ROOT") or "").strip()
            env = _current_environment()
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

    decorated = _attach_submission_files(submission)
    return JSONResponse(decorated, status_code=201, headers=_cache_headers_success())


def _dev_try_process_pdf(*, root: str, storage_key: str, submission_id: str, course_id: str, task_id: str, student_sub: str) -> None:
    """Best-effort dev helper: render, persist pages, and mark extracted.

    Intent:
        In lokalen Umgebungen, in denen Uploads auf das Dateisystem geschrieben
        werden (STORAGE_VERIFY_ROOT), verarbeiten wir eingereichte PDFs sofort
        und speichern abgeleitete Seitenbilder unter einem stabilen Pfad.

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
    else:
        if kind == "image":
            if mime_type not in ALLOWED_IMAGE_MIME:
                return JSONResponse(
                    {"error": "bad_request", "detail": "mime_not_allowed"}, status_code=400, headers=_cache_headers_error()
                )
            accepted = sorted(list(ALLOWED_IMAGE_MIME))
        else:  # kind == "file"
            # Non-scratch tasks accept only PDFs in MVP.
            if mime_type != "application/pdf":
                return JSONResponse({"error": "bad_request", "detail": "mime_not_allowed"}, status_code=400, headers=_cache_headers_error())
            accepted = ["application/pdf"]

    # Build a storage key (lowercase path, no traversal) — the value is later
    # validated again at submission time with a strict regex.
    import time as _time
    from uuid import uuid4 as _uuid4
    student_sub = str(user.get("sub", "student")).lower()
    ts = int(_time.time() * 1000)
    if mime_type == "image/png":
        ext = ".png"
    elif mime_type == "image/jpeg":
        ext = ".jpg"
    elif mime_type == SCRATCH_SB3_MIME:
        ext = ".sb3"
    elif mime_type == MAKECODE_HEX_MIME:
        ext = ".hex"
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
    adapter = STORAGE_ADAPTER
    # Lazy wiring: if adapter is not ready, try wiring once now.
    if isinstance(adapter, NullStorageAdapter):
        try:
            _wire_storage()
        except Exception:
            # Non-fatal; fall through to stub/503 handling.
            pass
        adapter = STORAGE_ADAPTER  # refresh after potential wiring

    # Dev fallback when adapter remains unavailable.
    if not bucket or isinstance(adapter, NullStorageAdapter):
        if _dev_upload_stub_enabled():
            presign_url = f"/api/learning/internal/upload-stub?storage_key={_quote(storage_key)}"
            from datetime import datetime, timezone, timedelta
            intent = {
                "intent_id": str(_uuid4()),
                "storage_key": storage_key,
                "url": presign_url,
                "headers": {"Content-Type": mime_type},
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
    # Normalize response headers to lower-case keys for stability across clients.
    # Provide both canonical casings for compatibility with tests and clients.
    headers_out = {}
    for k, v in dict(headers_src).items():
        lk = str(k).lower()
        headers_out[lk] = v
        if lk == "content-type":
            headers_out["Content-Type"] = v
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
        adapter=STORAGE_ADAPTER,
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
    if not url:
        return None
    # Defense-in-depth: allowlist known storage hosts only (avoid SSRF).
    try:
        env = (_current_environment() or "").strip().lower()
        allow_insecure_env = env in {"dev", "development", "test", "testing", "local"}
        supabase_base = (os.getenv("SUPABASE_URL") or "").strip()
        public_base = (os.getenv("SUPABASE_PUBLIC_URL") or "").strip()

        def _is_private_host(host: str) -> bool:
            """Return True when host resolves to loopback/private IPs.

            Why:
                Local stacks run with production-like settings (local=prod) while
                the internal Supabase gateway (Kong) is typically reachable only
                via HTTP on a private Docker network. We still want to allow
                server-side downloads in that scenario without allowing arbitrary
                plaintext HTTP to the public internet.
            """
            h = (host or "").strip().lower()
            if not h:
                return False
            if h in {"127.0.0.1", "localhost", "::1", "host.docker.internal"}:
                return True
            try:
                import ipaddress

                ip = ipaddress.ip_address(h)
                return bool(ip.is_loopback or ip.is_private)
            except ValueError:
                pass
            try:
                import socket

                infos = socket.getaddrinfo(h, None)
            except OSError:
                return False
            if not infos:
                return False
            try:
                import ipaddress
            except Exception:
                return False
            for family, _socktype, _proto, _canon, sockaddr in infos:
                ip_str = sockaddr[0] if isinstance(sockaddr, (tuple, list)) and sockaddr else ""
                try:
                    ip = ipaddress.ip_address(str(ip_str))
                except ValueError:
                    return False
                if not (ip.is_loopback or ip.is_private):
                    return False
            return True

        def _origin(raw: str) -> tuple[str, str, int] | None:
            parsed = _urlparse(raw)
            scheme = (parsed.scheme or "").lower()
            host = (parsed.hostname or "").lower()
            if scheme not in {"http", "https"} or not host:
                return None
            port = parsed.port or (443 if scheme == "https" else 80)
            return (scheme, host, int(port))

        sup_origin = _origin(supabase_base)
        pub_origin = _origin(public_base)
        sup_host = sup_origin[1] if sup_origin else ""
        pub_host = pub_origin[1] if pub_origin else ""
        target = _urlparse(url)
        if (target.scheme or "").lower() not in {"http", "https"}:
            return None
        tgt_scheme = (target.scheme or "").lower()
        if (not allow_insecure_env) and tgt_scheme != "https":
            return None
        tgt_host = (target.hostname or "").lower()
        tgt_port = target.port or (443 if tgt_scheme == "https" else 80)
        allowed_origins = {o for o in (sup_origin, pub_origin) if o is not None}
        if not allowed_origins or ((tgt_scheme, tgt_host, int(tgt_port)) not in allowed_origins):
            return None
        path = target.path or "/"
        while "//" in path:
            path = path.replace("//", "/")
        if ".." in path or re.search(r"%2e", path, flags=re.IGNORECASE):
            return None
        if not path.startswith("/storage/v1/object/"):
            return None
        # Prefer internal gateway for server-side downloads to avoid TLS trust
        # issues against the browser-facing host (e.g., local Caddy CA). If the
        # presigned URL uses the public host and an internal SUPABASE_URL exists,
        # rewrite scheme/host/port to the internal base while preserving path/query.
        if pub_origin and sup_origin and tgt_host == pub_host and supabase_base:
            try:
                internal = _urlparse(supabase_base)
                if internal.scheme and internal.netloc:
                    internal_scheme = (internal.scheme or "").lower()
                    internal_host = (internal.hostname or "").lower()
                    allow_http_internal = (internal_scheme == "http") and _is_private_host(internal_host)
                    if internal_scheme == "https" or allow_insecure_env or allow_http_internal:
                        url = target._replace(scheme=internal.scheme, netloc=internal.netloc).geturl()
            except Exception:
                pass
        effective = _urlparse(url)
        eff_scheme = (effective.scheme or "").lower()
        if (not allow_insecure_env) and eff_scheme != "https":
            eff_host = (effective.hostname or "").lower()
            eff_port = effective.port or (443 if eff_scheme == "https" else 80)
            # Allow internal HTTP only for the configured SUPABASE_URL origin
            # when it clearly stays on private/loopback networks (local=prod).
            if not (sup_origin and (eff_scheme, eff_host, int(eff_port)) == sup_origin and _is_private_host(eff_host)):
                return None
    except Exception:
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
            async with client.stream("GET", url, headers=headers) as resp:
                code = int(getattr(resp, "status_code", 500))
                if 300 <= code < 400:
                    return None
                if code >= 400:
                    return None
                out = bytearray()
                async for chunk in resp.aiter_bytes():
                    if not chunk:
                        continue
                    out.extend(chunk)
                    if len(out) > int(max_bytes):
                        return None
                return bytes(out)
    except Exception:
        return None


async def _load_storage_bytes_for_validation(*, storage_key: str, max_bytes: int) -> bytes | None:
    """Fetch bytes for validation either from local verify root or via presigned download."""
    root = (os.getenv("STORAGE_VERIFY_ROOT") or "").strip()
    local = _load_local_storage_bytes_for_validation(root=root, storage_key=storage_key, max_bytes=max_bytes)
    if local is not None:
        return local

    bucket = _storage_bucket()
    adapter = STORAGE_ADAPTER
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

    # Resolve target path safely beneath STORAGE_VERIFY_ROOT
    root = (os.getenv("STORAGE_VERIFY_ROOT") or "").strip()
    if not root:
        # Default dev directory inside project workspace
        root = os.path.abspath(".tmp/dev_uploads")
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
        _emit_upload_proxy_telemetry(
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
        _emit_upload_proxy_telemetry(
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
        resp = await _async_forward_upload(
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
    _emit_upload_proxy_telemetry(
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

    decorated = [_attach_submission_files(submission) for submission in submissions]
    return JSONResponse(decorated, status_code=200, headers=_cache_headers_success())
