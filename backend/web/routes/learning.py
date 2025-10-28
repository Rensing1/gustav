"""Learning (Lernen) API routes."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.learning.repo_db import DBLearningRepo
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


def _cache_headers_success() -> dict[str, str]:
    # Success responses: private and explicitly non-storable (defense-in-depth
    # against history stores and intermediary caches potentially keeping PII).
    return {"Cache-Control": "private, no-store"}


def _cache_headers_error() -> dict[str, str]:
    # Error responses: must never be stored; protects PII-bearing error pages.
    return {"Cache-Control": "private, no-store"}


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


def _is_same_origin(request: Request) -> bool:
    """CSRF defense-in-depth: verify same-origin via Origin or Referer.

    Behavior:
    - If `Origin` header is present, require exact match of scheme/host/port
      vs. server origin (proxy-aware when `GUSTAV_TRUST_PROXY=true`).
    - Else if `Referer` header is present, apply the same comparison using the
      referer's origin (path is ignored).
    - Else (no headers): allow to avoid breaking non-browser clients.
    """
    origin_val = request.headers.get("origin")
    try:
        from urllib.parse import urlparse
        import os

        def parse_origin(url: str) -> tuple[str, str, int]:
            p = urlparse(url)
            if not p.scheme or not p.hostname:
                raise ValueError("invalid_origin")
            scheme = p.scheme.lower()
            host = p.hostname.lower()
            port = p.port
            if port is None:
                port = 443 if scheme == "https" else 80
            return scheme, host, int(port)

        def parse_server(request: Request) -> tuple[str, str, int]:
            """Resolve the server origin for CSRF checks.

            Trust `X-Forwarded-*` only when explicitly enabled. Otherwise rely on
            ASGI's URL/Host to avoid header spoofing when running without a proxy.
            """
            trust_proxy = (os.getenv("GUSTAV_TRUST_PROXY", "false") or "").lower() == "true"

            if trust_proxy:
                xf_proto_raw = request.headers.get("x-forwarded-proto") or request.url.scheme or ""
                xf_host_raw = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
                xf_proto = xf_proto_raw.split(",")[0].strip()
                xf_host = xf_host_raw.split(",")[0].strip()
                scheme = (xf_proto or request.url.scheme or "http").lower()
                # xf_host or host may include port
                if ":" in xf_host:
                    host_only, port_str = xf_host.rsplit(":", 1)
                    try:
                        port = int(port_str)
                    except Exception:
                        port = 443 if scheme == "https" else 80
                    host = host_only.lower()
                else:
                    host = (xf_host or (request.url.hostname or "")).lower()
                    port = int(request.url.port) if request.url.port else (443 if scheme == "https" else 80)
                xf_port_raw = request.headers.get("x-forwarded-port") or ""
                if xf_port_raw:
                    try:
                        port = int(xf_port_raw.split(",")[0].strip())
                    except Exception:
                        port = 443 if scheme == "https" else 80
                return scheme, host, port

            # Not trusting proxy headers: derive strictly from ASGI request URL
            # to avoid relying on potentially spoofed Host header values.
            scheme = (request.url.scheme or "http").lower()
            host = (request.url.hostname or "").lower()
            port = int(request.url.port) if request.url.port else (443 if scheme == "https" else 80)
            return scheme, host, port

        s_scheme, s_host, s_port = parse_server(request)

        if origin_val:
            o_scheme, o_host, o_port = parse_origin(origin_val)
            return (o_scheme == s_scheme) and (o_host == s_host) and (o_port == s_port)

        # Fallback: use Referer when Origin is missing (some browsers)
        referer_val = request.headers.get("referer")
        if referer_val:
            r_scheme, r_host, r_port = parse_origin(referer_val)
            return (r_scheme == s_scheme) and (r_host == s_host) and (r_port == s_port)

        # No Origin/Referer -> allow non-browser clients
        return True
    except Exception:
        return False


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
    if not isinstance(payload, dict):
        raise ValueError("invalid_input")
    kind = payload.get("kind")
    if kind not in ("text", "image"):
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
    else:
        # Image submissions require finalized storage metadata
        required = {"storage_key", "mime_type", "size_bytes", "sha256"}
        if not required.issubset(payload.keys()):
            raise ValueError("invalid_image_payload")
        size_bytes = payload.get("size_bytes")
        try:
            size_int = int(size_bytes)
        except (TypeError, ValueError):
            raise ValueError("invalid_image_payload") from None
        if size_int <= 0:
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

    # CSRF defense-in-depth: if Origin header is present and not same-origin -> 403
    if not _is_same_origin(request):
        return JSONResponse(
            {"error": "forbidden", "detail": "csrf_violation"},
            status_code=403,
            headers=_cache_headers_error(),
        )

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

    try:
        kind, clean_payload = _validate_submission_payload(payload)
    except ValueError as exc:
        detail = str(exc) if str(exc) else "invalid_input"
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
