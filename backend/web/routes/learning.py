"""Learning (Lernen) API routes."""

from __future__ import annotations

import sys
from pathlib import Path
import re
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.learning.repo_db import DBLearningRepo
from backend.learning.usecases.sections import ListSectionsInput, ListSectionsUseCase
from backend.learning.usecases.submissions import (
    CreateSubmissionInput,
    CreateSubmissionUseCase,
    ListSubmissionsInput,
    ListSubmissionsUseCase,
)


learning_router = APIRouter(tags=["Learning"])


def _cache_headers() -> dict[str, str]:
    return {"Cache-Control": "private, max-age=0"}


def _current_user(request: Request) -> dict | None:
    user = getattr(request.state, "user", None)
    return user if isinstance(user, dict) else None


def _require_student(request: Request):
    user = _current_user(request)
    if not user:
        return None, JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_cache_headers())
    roles = user.get("roles") or []
    if not isinstance(roles, list) or "student" not in roles:
        return None, JSONResponse({"error": "forbidden"}, status_code=403, headers=_cache_headers())
    return user, None


def _is_same_origin(request: Request) -> bool:
    """CSRF defense-in-depth: verify `Origin` matches server origin.

    - If `Origin` header is absent: allow (non-browser clients).
    - If present: compare scheme, host, and effective port against server
      origin derived from `X-Forwarded-Proto`/`X-Forwarded-Host` (if present)
      or FastAPI's request URL and Host header. Ports default to 80/443 when
      not explicitly specified.
    """
    origin_val = request.headers.get("origin")
    if not origin_val:
        return True
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
                return scheme, host, port

            # Not trusting proxy headers: use request URL/Host only
            scheme = (request.url.scheme or "http").lower()
            host = (request.url.hostname or (request.headers.get("host") or "")).lower()
            port = int(request.url.port) if request.url.port else (443 if scheme == "https" else 80)
            # If Host header includes a port, normalize it
            if ":" in host:
                host_only, port_str = host.rsplit(":", 1)
                host = host_only
                try:
                    port = int(port_str)
                except Exception:
                    port = 443 if scheme == "https" else 80
            return scheme, host, port

        o_scheme, o_host, o_port = parse_origin(origin_val)
        s_scheme, s_host, s_port = parse_server(request)
        return (o_scheme == s_scheme) and (o_host == s_host) and (o_port == s_port)
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


def _normalize_limit(value: int) -> int:
    return max(1, min(value, 100))


def _normalize_offset(value: int) -> int:
    return max(0, value)


REPO = DBLearningRepo()
LIST_SECTIONS_USECASE = ListSectionsUseCase(REPO)
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
    global REPO, LIST_SECTIONS_USECASE, CREATE_SUBMISSION_USECASE, LIST_SUBMISSIONS_USECASE
    REPO = repo
    LIST_SECTIONS_USECASE = ListSectionsUseCase(repo)
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
    user, error = _require_student(request)
    if error:
        return error

    try:
        UUID(course_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers())

    try:
        include_materials, include_tasks = _parse_include(include)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_include"}, status_code=400, headers=_cache_headers())

    input_data = ListSectionsInput(
        student_sub=str(user.get("sub", "")),
        course_id=course_id,
        include_materials=include_materials,
        include_tasks=include_tasks,
        limit=_normalize_limit(limit),
        offset=_normalize_offset(offset),
    )

    try:
        sections = LIST_SECTIONS_USECASE.execute(input_data)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_cache_headers())
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers())

    return JSONResponse(sections, headers=_cache_headers())


def _validate_submission_payload(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("invalid_input")
    kind = payload.get("kind")
    if kind not in ("text", "image"):
        raise ValueError("invalid_input")
    if kind == "text":
        text_body = payload.get("text_body")
        if not isinstance(text_body, str) or not text_body.strip():
            raise ValueError("invalid_text_body")
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
        if mime_type not in ("image/jpeg", "image/png"):
            raise ValueError("invalid_image_payload")
        storage_key = payload.get("storage_key")
        if not isinstance(storage_key, str) or not storage_key:
            raise ValueError("invalid_image_payload")
        # Restrict to path-like storage keys (defense-in-depth):
        # - allow only lower-case, digits, _, ., /, -
        # - first char must be [a-z0-9]
        # - explicitly forbid any ".." sequence to avoid traversal-like patterns
        if not re.fullmatch(r"(?!(?:.*\.\.))[a-z0-9][a-z0-9_./\-]{0,255}", storage_key):
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
    user, error = _require_student(request)
    if error:
        return error

    # CSRF defense-in-depth: if Origin header is present and not same-origin -> 403
    if not _is_same_origin(request):
        return JSONResponse(
            {"error": "forbidden", "detail": "csrf_violation"},
            status_code=403,
            headers=_cache_headers(),
        )

    try:
        UUID(course_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers())
    try:
        UUID(task_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers())

    idempotency_key = request.headers.get("Idempotency-Key")
    # Contract: Idempotency-Key must be ≤ 64 characters when provided
    if idempotency_key is not None and len(idempotency_key) > 64:
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_input"},
            status_code=400,
            headers=_cache_headers(),
        )

    try:
        kind, clean_payload = _validate_submission_payload(payload)
    except ValueError as exc:
        detail = str(exc) if str(exc) else "invalid_input"
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400, headers=_cache_headers())

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
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_cache_headers())
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers())
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400, headers=_cache_headers())

    return JSONResponse(submission, status_code=201, headers=_cache_headers())


@learning_router.get("/api/learning/courses/{course_id}/tasks/{task_id}/submissions")
async def list_submissions(
    request: Request,
    course_id: str,
    task_id: str,
    limit: int = 20,
    offset: int = 0,
):
    """Return the caller's submission history for a task (student-only)."""
    user, error = _require_student(request)
    if error:
        return error

    try:
        UUID(course_id)
        UUID(task_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers())

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
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_cache_headers())
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers())

    return JSONResponse(submissions, status_code=200, headers=_cache_headers())
