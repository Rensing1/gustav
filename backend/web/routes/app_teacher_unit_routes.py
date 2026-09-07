"""Teacher unit workspace Browser-BFF routes.

Why:
    The app router is the compatibility facade for SvelteKit BFF read models.
    The workspace uses an explicit service. Legacy helpers below still serve
    the separate Live and Diagnostics routes until their own migration.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.teaching.services.unit_workspace import (
    UnitWorkspaceService,
    WorkspaceAccessDenied,
    WorkspaceInvalidSelection,
    WorkspaceNotFound,
    WorkspaceRepositoryIncomplete,
)
from backend.web.routes import teaching as teaching_routes
from backend.web.routes.app_session_helpers import (
    current_user as _current_user,
)
from backend.web.routes.app_session_helpers import (
    private_headers as _private_headers,
)
from backend.web.routes.app_session_helpers import (
    user_payload as _user_payload,
)
from backend.web.security.guards import has_any_role
from backend.web.teacher_workspace_providers import teacher_workspace_providers

app_teacher_unit_router = APIRouter(tags=["App"])


def _list_teacher_course_units(course_id: str, owner_sub: str) -> list[dict]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    return repo.list_course_units_for_owner(course_id, owner_sub)


def _field_value(item: object, key: str) -> object:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _list_unit_task_ids(unit_id: str, owner_sub: str) -> list[str]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    task_ids: list[str] = []
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        if isinstance(repo, DBTeachingRepo):
            sections = repo.list_sections_for_author(unit_id, owner_sub)
            for section in sections:
                section_tasks = repo.list_tasks_for_section_owned(
                    unit_id, str(section.get("id") or ""), owner_sub
                )
                for task in section_tasks:
                    task_id = str(task.get("id") or "")
                    if task_id:
                        task_ids.append(task_id)
            return task_ids
    except Exception:
        pass

    try:
        section_ids = [
            sid
            for sid, data in repo.sections.items()
            if str(getattr(data, "unit_id", "")) == unit_id
        ]
        section_ids.sort(key=lambda sid: int(getattr(repo.sections[sid], "position", 0)))
        for section_id in section_ids:
            for task_id in repo.task_ids_by_section.get(section_id, []):
                if task_id:
                    task_ids.append(str(task_id))
    except Exception:
        return []
    return task_ids


def _list_submission_pairs_for_students(
    course_id: str,
    owner_sub: str,
    student_subs: list[str],
    task_ids: list[str],
) -> set[tuple[str, str]]:
    if not student_subs or not task_ids:
        return set()

    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        if isinstance(repo, DBTeachingRepo):
            return repo.list_submission_pairs_for_students(
                owner_sub=owner_sub,
                course_id=course_id,
                student_subs=student_subs,
                task_ids=task_ids,
            )
    except Exception:
        return set()
    return set()


def _find_course_unit(course_id: str, owner_sub: str, unit_id: str) -> dict[str, object] | None:
    for item in _list_teacher_course_units(course_id, owner_sub):
        if not isinstance(item, dict):
            continue
        if str(item.get("id") or "") == unit_id:
            return item
    return None


@app_teacher_unit_router.get("/api/teaching/views/units/{unit_id}/workspace")
def get_teacher_unit_workspace(
    request: Request,
    unit_id: str,
    section_id: str | None = None,
    phase_id: str | None = None,
    module_id: str | None = None,
    edge_from_module_id: str | None = None,
    edge_to_module_id: str | None = None,
):
    """Read an author's workspace; synchronous DB work runs in the threadpool."""
    user = _current_user(request)
    if user is None:
        return JSONResponse(
            {"error": "unauthenticated"}, status_code=401, headers=_private_headers()
        )
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())
    try:
        UUID(unit_id)
    except (ValueError, TypeError):
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_unit_id"},
            status_code=400,
            headers=_private_headers(),
        )

    service = UnitWorkspaceService(teacher_workspace_providers(request).repository())
    try:
        body = service.read(
            str(user.get("sub") or ""),
            unit_id,
            section_id=section_id,
            phase_id=phase_id,
            module_id=module_id,
            edge_from_module_id=edge_from_module_id,
            edge_to_module_id=edge_to_module_id,
        )
    except WorkspaceAccessDenied:
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())
    except WorkspaceNotFound:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())
    except WorkspaceRepositoryIncomplete:
        return JSONResponse(
            {"error": "service_unavailable"}, status_code=503, headers=_private_headers()
        )
    except WorkspaceInvalidSelection as exc:
        return JSONResponse(
            {"error": "bad_request", "detail": str(exc)},
            status_code=400,
            headers=_private_headers(),
        )
    return JSONResponse({"user": _user_payload(user), **body}, headers=_private_headers())
