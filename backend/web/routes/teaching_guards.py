"""Shared Teaching authorization and write-safety guards."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.teaching.errors import TeachingRepositoryUnavailable
from backend.web.routes.security import _is_same_origin
from backend.web.routes.teaching_shared import _is_uuid_like, _private_error


_repo_provider: Callable[[], Any] | None = None


def configure_teaching_guard_repo_provider(provider: Callable[[], Any]) -> None:
    """Install the repository provider used by Teaching guards."""

    global _repo_provider
    _repo_provider = provider


def _get_repo(provider: Callable[[], Any] | None = None) -> Any:
    active_provider = provider or _repo_provider
    if active_provider is None:
        raise RuntimeError("teaching_guard_repo_provider_not_configured")
    return active_provider()


def _guard_unit_author(
    unit_id: str,
    author_sub: str,
    *,
    repo_provider: Callable[[], Any] | None = None,
) -> JSONResponse | None:
    """Validate unit ownership, returning an error response when access is denied."""

    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        repo = _get_repo(repo_provider)
        if isinstance(repo, DBTeachingRepo):
            if repo.unit_exists_for_author(unit_id, author_sub):
                return None
            exists = repo.unit_exists(unit_id)
            if exists is False:
                return _private_error({"error": "not_found"}, status_code=404)
            return _private_error({"error": "forbidden"}, status_code=403)
    except TeachingRepositoryUnavailable:
        raise
    except Exception:
        return _private_error({"error": "forbidden"}, status_code=403)

    repo = _get_repo(repo_provider)
    if hasattr(repo, "unit_exists_for_author") and repo.unit_exists_for_author(unit_id, author_sub):
        return None
    if hasattr(repo, "unit_exists") and not repo.unit_exists(unit_id):
        return _private_error({"error": "not_found"}, status_code=404)
    return _private_error({"error": "forbidden"}, status_code=403)


def _guard_course_owner(
    course_id: str,
    owner_sub: str,
    *,
    repo_provider: Callable[[], Any] | None = None,
) -> JSONResponse | None:
    """Validate caller ownership of a course, returning JSON errors when denied."""

    if not course_id or not owner_sub:
        return _private_error({"error": "forbidden"}, status_code=403)

    repo = _get_repo(repo_provider)

    # Prefer explicit DB ownership query when available because it short-circuits
    # with stable security semantics and avoids fetching full course payloads.
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        if isinstance(repo, DBTeachingRepo):
            if repo.course_exists_for_owner(course_id, owner_sub):
                return None
            if repo.course_exists(course_id) is False:
                return _private_error({"error": "not_found"}, status_code=404)
            return _private_error({"error": "forbidden"}, status_code=403)
    except TeachingRepositoryUnavailable:
        raise
    except Exception:
        return _private_error({"error": "forbidden"}, status_code=403)

    # Fallback for in-memory/test repos: fetch the row and compare teacher_id.
    try:
        course = repo.get_course(course_id)
        if not course:
            return _private_error({"error": "not_found"}, status_code=404)
        owner_id = (
            course.get("teacher_id")
            if isinstance(course, dict)
            else getattr(course, "teacher_id", None)
        )
        if owner_id != owner_sub:
            return _private_error({"error": "forbidden"}, status_code=403)
        return None
    except TeachingRepositoryUnavailable:
        raise
    except Exception:
        return _private_error({"error": "forbidden"}, status_code=403)


def _csrf_guard(request: Request) -> JSONResponse | None:
    """Strict CSRF guard for browser-origin write requests."""

    if getattr(request.state, "cli_token_id", None):
        return None
    origin_present = request.headers.get("origin") or request.headers.get("referer")
    if not origin_present or (not _is_same_origin(request)):
        return _private_error({"error": "forbidden", "detail": "csrf_violation"}, status_code=403, vary_origin=True)
    return None


def _require_strict_same_origin(request: Request) -> bool:
    """Return True only when a same-origin indicator is present and matches."""

    origin_present = request.headers.get("origin") or request.headers.get("referer")
    if not origin_present:
        return False
    return _is_same_origin(request)
