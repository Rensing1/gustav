"""Learning (Lernen) API routes."""

from __future__ import annotations

import re
from typing import Any
import os
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


learning_router = APIRouter(tags=["Learning"])

# Compiled pattern for path-like storage keys used in image submissions.
# Rules:
# - first char: [a-z0-9]
# - allowed chars: lower-case letters, digits, underscore, dot, slash, dash
# - forbid any ".." segment (defense-in-depth against traversal-like patterns)
STORAGE_KEY_RE = re.compile(r"(?!(?:.*\.\.))[a-z0-9][a-z0-9_./\-]{0,255}")

# Whitelist for image MIME types accepted by the submissions endpoint.
ALLOWED_IMAGE_MIME: set[str] = {"image/jpeg", "image/png"}
# Allow PDF as document submission type in MVP.
# Rationale: Simpler security model (no macro-enabled formats) and reliable preview pipeline.
ALLOWED_FILE_MIME: set[str] = {"application/pdf"}
# Upper bound for binary submissions (defense-in-depth; API also constrains contractually).
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MiB


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


def _current_user(request: Request) -> dict | None:
    user = getattr(request.state, "user", None)
    return user if isinstance(user, dict) else None


def _require_student(request: Request):
    user = _current_user(request)
    if not user:
        return None, JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_cache_headers_error())
    roles = user.get("roles") or []
    if not isinstance(roles, list) or "student" not in roles:
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


REPO = DBLearningRepo()
LIST_SECTIONS_USECASE = ListSectionsUseCase(REPO)
LIST_UNIT_SECTIONS_USECASE = ListUnitSectionsUseCase(REPO)
LIST_COURSES_USECASE = ListCoursesUseCase(REPO)
LIST_COURSE_UNITS_USECASE = ListCourseUnitsUseCase(REPO)
CREATE_SUBMISSION_USECASE = CreateSubmissionUseCase(REPO)
LIST_SUBMISSIONS_USECASE = ListSubmissionsUseCase(REPO)

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
    global REPO, LIST_SECTIONS_USECASE, LIST_UNIT_SECTIONS_USECASE, LIST_COURSES_USECASE, LIST_COURSE_UNITS_USECASE, CREATE_SUBMISSION_USECASE, LIST_SUBMISSIONS_USECASE
    REPO = repo
    LIST_SECTIONS_USECASE = ListSectionsUseCase(repo)
    LIST_UNIT_SECTIONS_USECASE = ListUnitSectionsUseCase(repo)
    LIST_COURSES_USECASE = ListCoursesUseCase(repo)
    LIST_COURSE_UNITS_USECASE = ListCourseUnitsUseCase(repo)
    CREATE_SUBMISSION_USECASE = CreateSubmissionUseCase(repo)
    LIST_SUBMISSIONS_USECASE = ListSubmissionsUseCase(repo)


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
        sections = LIST_SECTIONS_USECASE.execute(input_data)
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
    items = LIST_COURSES_USECASE.execute(
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
        rows = LIST_COURSE_UNITS_USECASE.execute(
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
        sections = LIST_UNIT_SECTIONS_USECASE.execute(input_data)
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
        if size_int <= 0 or size_int > MAX_UPLOAD_BYTES:
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
        if size_int <= 0 or size_int > MAX_UPLOAD_BYTES:
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
    user, error = _require_student(request)
    if error:
        return error

    # CSRF defense: configurable strict mode. When STRICT_CSRF_SUBMISSIONS=true,
    # require Origin/Referer presence and same-origin; otherwise only reject when
    # a non-matching Origin/Referer is present.
    strict = (os.getenv("STRICT_CSRF_SUBMISSIONS", "false") or "").lower() == "true"
    check_ok = _require_strict_same_origin(request) if strict else _is_same_origin(request)
    if not check_ok:
        return JSONResponse({"error": "forbidden", "detail": "csrf_violation"}, status_code=403, headers=_cache_headers_error())

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
        submission = CREATE_SUBMISSION_USECASE.execute(submission_input)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_cache_headers_error())
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400, headers=_cache_headers_error())

    return JSONResponse(submission, status_code=201, headers=_cache_headers_success())


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
    user, error = _require_student(request)
    if error:
        return error
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
    if size_int <= 0 or size_int > MAX_UPLOAD_BYTES:
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
        _ = LIST_SUBMISSIONS_USECASE.execute(
            ListSubmissionsInput(
                course_id=str(course_id),
                task_id=str(task_id),
                student_sub=str(user.get("sub", "")),
                limit=1,
                offset=0,
            )
        )
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_cache_headers_error())
    except LookupError:
        # Task not visible (or course/unit mismatch) should not leak existence
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    # Build a storage key (lowercase path, no traversal) — the value is later
    # validated again at submission time with a strict regex.
    import time as _time
    from uuid import uuid4 as _uuid4
    student_sub = str(user.get("sub", "student")).lower()
    ts = int(_time.time())
    ext = ".png" if mime_type == "image/png" else (".jpg" if mime_type == "image/jpeg" else ".pdf")
    storage_key = f"submissions/{course_id}/{task_id}/{student_sub}/{ts}-{_uuid4().hex}{ext}"
    if not STORAGE_KEY_RE.fullmatch(storage_key):
        storage_key = f"submissions/{_uuid4().hex}{ext}"

    # Stub presigned URL (adapter optional in MVP)
    from datetime import datetime, timezone, timedelta
    intent = {
        "intent_id": str(_uuid4()),
        "storage_key": storage_key,
        "url": "http://upload.local/stub",
        "headers": {"Content-Type": mime_type},
        "accepted_mime_types": accepted,
        "max_size_bytes": MAX_UPLOAD_BYTES,
        # Short-lived expiry (defense-in-depth): 10 minutes from now (UTC)
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(timespec="seconds"),
    }
    return JSONResponse(intent, status_code=200, headers=_cache_headers_success())


def _verify_storage_object(storage_key: str, sha256: str, size_bytes: int, mime_type: str) -> tuple[bool, str]:
    """Verify object integrity against a local storage root if configured.

    Why:
        Clients may report incorrect metadata (size/hash). To keep the MVP
        simple and offline-friendly, we verify against a local directory when
        `STORAGE_VERIFY_ROOT` is set. In production this should use the storage
        provider's HEAD/etag and/or a trusted hash pipeline.

    Behavior:
        - If no `STORAGE_VERIFY_ROOT` is set, return (True, 'skipped') unless
          REQUIRE_STORAGE_VERIFY=true mandates verification.
        - Ensures the resolved path stays within the configured root.
        - Compares actual size and sha256 of the file with the payload.
    """
    import os
    from hashlib import sha256 as _sha256
    from pathlib import Path

    root = (os.getenv("STORAGE_VERIFY_ROOT") or "").strip()
    require = (os.getenv("REQUIRE_STORAGE_VERIFY", "false") or "").lower() == "true"
    if not root:
        return (not require, "skipped")
    if not storage_key or not sha256 or size_bytes is None:
        return (False, "missing_fields")
    base = Path(root).resolve()
    target = (base / storage_key).resolve()
    try:
        common = os.path.commonpath([str(base), str(target)])
    except Exception:
        return (False, "path_error")
    if common != str(base):
        return (False, "path_escape")
    if not target.exists() or not target.is_file():
        return (False, "missing_file")
    actual_size = target.stat().st_size
    if int(actual_size) != int(size_bytes):
        return (False, "size_mismatch")
    h = _sha256()
    with target.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    actual_hash = h.hexdigest()
    if actual_hash.lower() != str(sha256).lower():
        return (False, "hash_mismatch")
    return (True, "ok")

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
        submissions = LIST_SUBMISSIONS_USECASE.execute(input_data)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_cache_headers_error())
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())

    return JSONResponse(submissions, status_code=200, headers=_cache_headers_success())
