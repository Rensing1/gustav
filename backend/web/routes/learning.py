"""Learning (Lernen) API routes."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

try:
    from backend.learning.repo_db import DBLearningRepo
    from backend.learning.usecases.sections import ListSectionsInput, ListSectionsUseCase
    from backend.learning.usecases.submissions import (
        CreateSubmissionInput,
        CreateSubmissionUseCase,
    )
except ModuleNotFoundError:
    root_candidate = None
    current = Path(__file__).resolve()
    for candidate in current.parents:
        if (
            (candidate / "backend" / "learning" / "repo_db.py").exists()
            and (candidate / "backend" / "identity_access").exists()
        ):
            root_candidate = candidate
            break
        if (
            (candidate / "backend" / "learning" / "repo_db.py").exists()
            and (candidate / "backend" / "tests").exists()
        ):
            root_candidate = candidate
            break
    if root_candidate:
        sys.path.insert(0, str(root_candidate))
        sys.modules.pop("backend", None)
        sys.modules.pop("backend.learning", None)
    from backend.learning.repo_db import DBLearningRepo
    from backend.learning.usecases.sections import ListSectionsInput, ListSectionsUseCase
    from backend.learning.usecases.submissions import (
        CreateSubmissionInput,
        CreateSubmissionUseCase,
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


def set_repo(repo) -> None:  # pragma: no cover - used in tests
    global REPO, LIST_SECTIONS_USECASE, CREATE_SUBMISSION_USECASE
    REPO = repo
    LIST_SECTIONS_USECASE = ListSectionsUseCase(repo)
    CREATE_SUBMISSION_USECASE = CreateSubmissionUseCase(repo)


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
        return JSONResponse({"error": "bad_request", "detail": "invalid_course_id"}, status_code=400)

    try:
        include_materials, include_tasks = _parse_include(include)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_include"}, status_code=400)

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
        storage_key = payload.get("storage_key")
        if not isinstance(storage_key, str) or not storage_key:
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

    try:
        UUID(course_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_course_id"}, status_code=400)
    try:
        UUID(task_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_task_id"}, status_code=400)

    idempotency_key = request.headers.get("Idempotency-Key")

    try:
        kind, clean_payload = _validate_submission_payload(payload)
    except ValueError as exc:
        detail = str(exc) if str(exc) else "invalid_input"
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400)

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
