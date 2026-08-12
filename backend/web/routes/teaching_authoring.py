"""Shared Teaching authoring helpers for module-backed content writes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from backend.web.routes import teaching_guards
from backend.web.routes.teaching_shared import (
    _current_sub,
    _is_uuid_like,
    _private_error,
    _require_teacher,
)


_repo_provider: Callable[[], Any] | None = None


def configure_teaching_authoring_repo_provider(provider: Callable[[], Any]) -> None:
    """Install the repository provider used by module authoring helpers."""

    global _repo_provider
    _repo_provider = provider


def _get_repo(provider: Callable[[], Any] | None = None) -> Any:
    active_provider = provider or _repo_provider
    if active_provider is None:
        raise RuntimeError("teaching_authoring_repo_provider_not_configured")
    return active_provider()


def _is_signature_compat_type_error(exc: TypeError) -> bool:
    """Return True only for argument-signature mismatches in fallback repos.

    Why:
        Some older/in-memory test doubles still expose positional signatures.
        We accept that compatibility case, but we must not mask arbitrary
        TypeErrors raised inside repository code paths.
    """

    msg = (str(exc) or "").lower()
    hints = (
        "unexpected keyword argument",
        "required positional argument",
        "positional arguments but",
        "takes",
        "got multiple values for argument",
    )
    return any(hint in msg for hint in hints)


def _get_unit_module_section_id_for_author(repo: object, *, unit_id: str, module_id: str, author_id: str) -> str | None:
    """Return the backing section id for an owned module.

    The section id is an internal storage detail. Module-scoped write routes use
    this helper so CLI clients do not need an extra read-scoped lookup.
    """

    try:
        try:
            module = repo.get_unit_module_for_author(unit_id=unit_id, module_id=module_id, author_id=author_id)  # type: ignore[attr-defined]
        except TypeError as exc:
            if not _is_signature_compat_type_error(exc):
                raise
            module = repo.get_unit_module_for_author(unit_id, module_id, author_id)  # type: ignore[attr-defined]
    except LookupError:
        raise
    except PermissionError:
        raise
    if not module:
        return None
    section_id = module.get("section_id") if isinstance(module, dict) else getattr(module, "section_id", None)
    return str(section_id) if section_id else None


def _resolve_module_section_for_authoring_mutation(
    request: Request,
    *,
    unit_id: str,
    module_id: str,
    task_id: str | None = None,
    repo_provider: Callable[[], Any] | None = None,
) -> tuple[str | None, Response | JSONResponse | None]:
    """Resolve a module-backed write/delete without requiring client read scope.

    Permissions:
        The caller must be an authenticated teacher and must own the unit.
        Browser-origin writes must pass the shared CSRF guard.
    """

    repo = _get_repo(repo_provider)
    user, error = _require_teacher(request)
    if error:
        return None, error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return None, csrf
    if not _is_uuid_like(unit_id):
        return None, _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(module_id):
        return None, _private_error({"error": "bad_request", "detail": "invalid_module_id"}, status_code=400)
    if task_id is not None and not _is_uuid_like(task_id):
        return None, _private_error({"error": "bad_request", "detail": "invalid_task_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=lambda: repo)
    if guard:
        return None, guard
    if not hasattr(repo, "get_unit_module_for_author"):
        return None, _private_error({"error": "service_unavailable", "detail": "modular_repo_unavailable"}, status_code=503)
    try:
        section_id = _get_unit_module_section_id_for_author(repo, unit_id=unit_id, module_id=module_id, author_id=sub)
    except LookupError:
        return None, _private_error({"error": "not_found"}, status_code=404)
    except PermissionError:
        return None, _private_error({"error": "forbidden"}, status_code=403)
    if not section_id:
        return None, _private_error({"error": "not_found"}, status_code=404)
    return section_id, None


def _resolve_module_section_for_authoring_read(
    request: Request,
    *,
    unit_id: str,
    module_id: str,
    repo_provider: Callable[[], Any] | None = None,
) -> tuple[str | None, Response | JSONResponse | None]:
    """Resolve an owned module to its backing section for one read request.

    Unlike mutation routes, this path deliberately has no CSRF check and only
    requires the CLI `read` scope. The section id stays an internal detail, so
    clients can list module tasks without making a hidden resolver request.
    """

    repo = _get_repo(repo_provider)
    user, error = _require_teacher(request)
    if error:
        return None, error
    if not _is_uuid_like(unit_id):
        return None, _private_error(
            {"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400
        )
    if not _is_uuid_like(module_id):
        return None, _private_error(
            {"error": "bad_request", "detail": "invalid_module_id"}, status_code=400
        )
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=lambda: repo)
    if guard:
        return None, guard
    if not hasattr(repo, "get_unit_module_for_author"):
        return None, _private_error(
            {"error": "service_unavailable", "detail": "modular_repo_unavailable"},
            status_code=503,
        )
    try:
        section_id = _get_unit_module_section_id_for_author(
            repo, unit_id=unit_id, module_id=module_id, author_id=sub
        )
    except LookupError:
        return None, _private_error({"error": "not_found"}, status_code=404)
    except PermissionError:
        return None, _private_error({"error": "forbidden"}, status_code=403)
    if not section_id:
        return None, _private_error({"error": "not_found"}, status_code=404)
    return section_id, None
