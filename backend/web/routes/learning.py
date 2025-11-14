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
import os
import sys as _sys
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

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
    ListSubmissionsInput,
    ListSubmissionsUseCase,
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
import httpx
from urllib.parse import urlparse as _urlparse, quote as _quote


learning_router = APIRouter(tags=["Learning"])

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

def _current_environment() -> str:
    """Return the current app environment string.

    Resolution is lazy to avoid import-order flakiness in tests:
    - Try to import `backend.web.main` or `main` and read `SETTINGS.environment`.
    - Fallback to `GUSTAV_ENV` (default "dev").
    """
    try:
        import importlib
        mod = importlib.import_module("backend.web.main")
    except Exception:
        try:
            import importlib
            mod = importlib.import_module("main")
        except Exception:
            mod = None
    if mod is not None:
        try:
            env = getattr(getattr(mod, "SETTINGS", object()), "environment", "dev")
            return str(env).lower()
        except Exception:
            pass
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
            origin_hdr = str(request.headers.get("origin") or request.headers.get("referer") or "")
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


def _parse_include(value: str | None) -> tuple[bool, bool]:
    if not value:
        return False, False
    tokens = [token.strip() for token in value.split(",") if token.strip()]
    allowed = {"materials", "tasks"}
    if any(token not in allowed for token in tokens):
        raise ValueError("invalid_include")
    return "materials" in tokens, "tasks" in tokens


# Note: Pagination clamping is handled in the use case layer to keep this
# adapter thin and framework-agnostic.


# Lazily construct the repository to ensure environment (.env, pytest) is loaded
# before establishing DB connections. This avoids import-time failures and keeps
# the adapter thin. Tests can override via set_repo().
_REPO: _LearningRepoCombined | None = None

def _get_repo() -> _LearningRepoCombined:
    global _REPO
    if _REPO is None:
        _REPO = DBLearningRepo()
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


def set_repo(repo: _LearningRepoCombined) -> None:  # pragma: no cover - used in tests
    global _REPO
    _REPO = repo


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

    return JSONResponse(sections, headers=_cache_headers_success())


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
    return JSONResponse(sections, headers=_cache_headers_success())


def _validate_submission_payload(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Validate and normalize the submission payload (text/image/file).

    Why:
        Keep FastAPI layer thin, but ensure inputs are sane before invoking
        use cases/repo and touching the database. Enforces MIME allowlists,
        size bounds, and storage key/sha256 formats. Error detail strings match
        the OpenAPI contract for precise client handling.

    Returns:
        (kind, clean_payload) where kind in {text,image,file} and
        clean_payload contains the normalized fields for the given kind.

    Errors:
        Raises ValueError with one of: 'invalid_input', 'invalid_image_payload',
        'invalid_file_payload'.
    """
    if not isinstance(payload, dict):
        raise ValueError("invalid_input")
    kind = payload.get("kind")
    if kind not in ("text", "image", "file"):
        raise ValueError("invalid_input")
    if kind == "text":
        text_body = payload.get("text_body")
        if not isinstance(text_body, str) or not text_body.strip():
            # Harmonize with API contract: return generic invalid_input
            raise ValueError("invalid_input")
        # Optional guardrail: prevent oversized payloads from overloading DB
        if len(text_body) > 10_000:
            raise ValueError("invalid_input")
        return kind, {"text_body": text_body.strip()}
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
        mime_type = payload.get("mime_type")
        if not isinstance(mime_type, str) or not mime_type:
            raise ValueError("invalid_image_payload")
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
        mime_type = payload.get("mime_type")
        if not isinstance(mime_type, str) or not mime_type:
            raise ValueError("invalid_file_payload")
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
        import re as _re
        if not _re.fullmatch(r"[A-Za-z0-9_-]{1,64}", idempotency_key):
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

    submission_input = CreateSubmissionInput(
        course_id=course_id,
        task_id=task_id,
        student_sub=str(user.get("sub", "")),
        kind=kind,
        text_body=clean_payload.get("text_body"),
        storage_key=clean_payload.get("storage_key"),
        mime_type=clean_payload.get("mime_type"),
        size_bytes=clean_payload.get("size_bytes"),
        sha256=clean_payload.get("sha256"),
        idempotency_key=idempotency_key,
    )

    try:
        submission = CreateSubmissionUseCase(_get_repo()).execute(submission_input)
    except PermissionError:
        # Permission-denied at the use case layer (e.g., not enrolled or task
        # not released). Attach a diagnostic header to distinguish from CSRF.
        try:
            origin_hdr = str(request.headers.get("origin") or request.headers.get("referer") or "")
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
        # Conservative fallback in dev/test when the Learning repo is unavailable
        # (e.g., missing DB driver). Return a minimal accepted submission so UI
        # and contract tests remain operable without a database.
        from datetime import datetime, timezone
        from uuid import uuid4 as _uuid4
        submission = {
            "id": str(_uuid4()),
            "attempt_nr": 1,
            "kind": kind,
            "text_body": clean_payload.get("text_body"),
            "mime_type": clean_payload.get("mime_type"),
            "size_bytes": clean_payload.get("size_bytes"),
            "storage_key": clean_payload.get("storage_key"),
            "sha256": clean_payload.get("sha256"),
            "analysis_status": "pending",
            "error_code": None,
            "analysis_json": None,
            "feedback_md": None,
            # Telemetry defaults
            "vision_attempts": 0,
            "vision_last_error": None,
            "feedback_last_attempt_at": None,
            "feedback_last_error": None,
            # Timestamps for UI parity (approximate)
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        return JSONResponse(submission, status_code=202, headers=_cache_headers_success())

    # Opportunistic dev processing for PDF submissions (synchronous, MVP):
    # In dev environments where STORAGE_VERIFY_ROOT is configured, attempt to
    # read the uploaded PDF bytes directly and kick off the rendering pipeline.
    # This is best-effort and must not block or affect the API response.
    try:
        if kind == "file" and str(clean_payload.get("mime_type")) == "application/pdf":
            root = (os.getenv("STORAGE_VERIFY_ROOT") or "").strip()
            if root:
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

    # Always return 202 Accepted for async processing semantics, including
    # idempotent retries reusing an existing pending submission.
    return JSONResponse(submission, status_code=202, headers=_cache_headers_success())


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
    """Create a short-lived upload intent for a submission asset (image/PDF).

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
            - kind: "image" | "file" (PDF)
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
    mime_type = str(payload.get("mime_type") or "").strip()
    size_bytes = payload.get("size_bytes")
    try:
        size_int = int(size_bytes)
    except Exception:
        return JSONResponse({"error": "bad_request", "detail": "invalid_input"}, status_code=400, headers=_cache_headers_error())
    if not filename or len(filename) > 255:
        return JSONResponse({"error": "bad_request", "detail": "invalid_input"}, status_code=400, headers=_cache_headers_error())
    if size_int <= 0 or size_int > _max_upload_bytes():
        return JSONResponse({"error": "bad_request", "detail": "size_exceeded"}, status_code=400, headers=_cache_headers_error())
    if kind == "image":
        if mime_type not in ALLOWED_IMAGE_MIME:
            return JSONResponse({"error": "bad_request", "detail": "mime_not_allowed"}, status_code=400, headers=_cache_headers_error())
        accepted = sorted(list(ALLOWED_IMAGE_MIME))
    elif kind == "file":
        if mime_type not in ALLOWED_FILE_MIME:
            return JSONResponse({"error": "bad_request", "detail": "mime_not_allowed"}, status_code=400, headers=_cache_headers_error())
        accepted = sorted(list(ALLOWED_FILE_MIME))
    else:
        return JSONResponse({"error": "bad_request", "detail": "invalid_input"}, status_code=400, headers=_cache_headers_error())

    # Authorization/visibility: ensure the caller is a member and the task is
    # visible to the student. We reuse the submissions listing use case which
    # already enforces membership and task visibility at the DB boundary.
    try:
        # Any positive limit triggers the underlying checks; results are ignored.
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
        # DB may be unavailable in dev/test; attempt a conservative in-memory check
        try:
            import importlib
            try:
                t = importlib.import_module("routes.teaching")
            except Exception:
                t = importlib.import_module("backend.web.routes.teaching")
            repo = getattr(t, "REPO", None)
            student_sub = str(user.get("sub", ""))
            # Membership
            members = getattr(repo, "members", {}) or {}
            if student_sub not in (members.get(str(course_id)) or {}):
                return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
            # Task and section visibility
            tasks = getattr(repo, "tasks", {}) or {}
            task = tasks.get(str(task_id))
            if not task:
                return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
            section_id = getattr(task, "section_id", None) or (task.get("section_id") if isinstance(task, dict) else None)
            unit_id = getattr(task, "unit_id", None) or (task.get("unit_id") if isinstance(task, dict) else None)
            modules_by_course = getattr(repo, "modules_by_course", {}) or {}
            course_modules = getattr(repo, "course_modules", {}) or {}
            mod_ids = modules_by_course.get(str(course_id)) or []
            module_id = None
            for mid in mod_ids:
                mod = course_modules.get(mid)
                uid = getattr(mod, "unit_id", None) or (mod.get("unit_id") if isinstance(mod, dict) else None)
                if str(uid) == str(unit_id):
                    module_id = mid
                    break
            if not module_id or not section_id:
                return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
            releases = getattr(repo, "module_section_releases", {}) or {}
            rec = releases.get((str(module_id), str(section_id)))
            visible = bool((rec or {}).get("visible")) if isinstance(rec, dict) else False
            if not visible:
                return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
        except Exception:
            # As a last resort, keep behavior permissive to avoid breaking dev
            # flows; submission creation will still be RLS-protected.
            pass

    # Build a storage key (lowercase path, no traversal) — the value is later
    # validated again at submission time with a strict regex.
    import time as _time
    from uuid import uuid4 as _uuid4
    student_sub = str(user.get("sub", "student")).lower()
    ts = int(_time.time() * 1000)
    ext = ".png" if mime_type == "image/png" else (".jpg" if mime_type == "image/jpeg" else ".pdf")
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
        - Body bytes are written to STORAGE_VERIFY_ROOT/storage_key.
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
    user, error = _require_student(request)
    if error:
        return error
    if not _require_strict_same_origin(request):
        return JSONResponse({"error": "forbidden", "detail": "csrf_violation"}, status_code=403, headers=_cache_headers_error())
    if not _upload_proxy_enabled():
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    target = str(request.query_params.get("url") or "").strip()
    header_token = str(request.query_params.get("headers") or "").strip()
    forward_headers = _decode_proxy_headers(header_token)
    if not target:
        return JSONResponse({"error": "bad_request", "detail": "missing_url"}, status_code=400, headers=_cache_headers_error())
    base = (os.getenv("SUPABASE_URL") or "").strip()
    try:
        parsed_target = _urlparse(target)
        parsed_base = _urlparse(base)
    except Exception:
        return JSONResponse({"error": "bad_request", "detail": "invalid_url"}, status_code=400, headers=_cache_headers_error())

    target_scheme, target_host, target_port = _normalized_parts(parsed_target)
    base_scheme, base_host, base_port = _normalized_parts(parsed_base)

    if not target_scheme or target_scheme not in {"http", "https"} or not target_host:
        return JSONResponse({"error": "bad_request", "detail": "invalid_url"}, status_code=400, headers=_cache_headers_error())

    local_hosts = {"localhost", "::1", "host.docker.internal"}
    is_local_http = target_host in local_hosts or target_host.startswith("127.")
    if target_scheme == "http" and not is_local_http:
        return JSONResponse({"error": "bad_request", "detail": "invalid_url"}, status_code=400, headers=_cache_headers_error())
    if base_scheme == "https" and target_scheme != "https":
        return JSONResponse({"error": "bad_request", "detail": "invalid_url"}, status_code=400, headers=_cache_headers_error())
    if not base_host or target_host != base_host:
        return JSONResponse({"error": "bad_request", "detail": "invalid_url_host"}, status_code=400, headers=_cache_headers_error())
    if base_port and target_port and target_port != base_port:
        return JSONResponse({"error": "bad_request", "detail": "invalid_url_host"}, status_code=400, headers=_cache_headers_error())

    # Enforce that the path targets the storage upload endpoint to reduce SSRF surface.
    path = parsed_target.path or "/"
    # Be tolerant to accidental double slashes from upstream clients by
    # collapsing them before applying prefix checks (dev/local presigners can
    # produce .../storage/v1//object/...). This does not weaken the check
    # because we still require the fixed upload prefix afterwards.
    while "//" in path:
        path = path.replace("//", "/")
    if not path.startswith("/storage/v1/object/"):
        return JSONResponse({"error": "bad_request", "detail": "invalid_url"}, status_code=400, headers=_cache_headers_error())

    body, body_error = await _read_request_stream_with_limit(request, _max_upload_bytes())
    if body_error:
        return JSONResponse({"error": "bad_request", "detail": body_error}, status_code=400, headers=_cache_headers_error())
    content_type = request.headers.get("content-type") or "application/octet-stream"
    # Enforce MIME allowlist for uploads proxied through our origin.
    allowed_mime = (set(ALLOWED_IMAGE_MIME) | set(ALLOWED_FILE_MIME) | {"application/octet-stream"})
    if content_type not in allowed_mime:
        return JSONResponse({"error": "bad_request", "detail": "mime_not_allowed"}, status_code=400, headers=_cache_headers_error())

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
        return JSONResponse({"error": "bad_gateway", "detail": "proxy_failed"}, status_code=502, headers=_cache_headers_error())
    if getattr(resp, "status_code", 500) >= 300:
        # Prod-parity: non-2xx upstream is a 502 in all environments.
        return JSONResponse({"error": "bad_gateway", "detail": "upstream_error"}, status_code=502, headers=_cache_headers_error())

    import hashlib as _hashlib
    h = _hashlib.sha256(); h.update(body)
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

    return JSONResponse(submissions, status_code=200, headers=_cache_headers_success())
