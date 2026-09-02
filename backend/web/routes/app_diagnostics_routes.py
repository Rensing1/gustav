"""Diagnostics Browser-BFF routes.

Why:
    Diagnostics read models combine course membership, unit/task progress, and
    learner summaries. Keeping them together outside app.py separates teaching
    diagnostics from session and live-dashboard composition.
"""

from __future__ import annotations

import sys as _sys

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.web.query_validation import parse_bounded_pagination
from backend.web.security.guards import has_any_role
from backend.web.routes import teaching as teaching_routes
from backend.web.routes import teaching_guards
from backend.web.routes.app_session_helpers import (
    current_user as _current_user,
    private_headers as _private_headers,
    user_payload as _user_payload,
)
from backend.web.routes.app_teacher_course_routes import (
    _get_teacher_course,
    _list_teacher_course_members,
)
from backend.web.routes.app_teacher_unit_routes import (
    _field_value,
    _list_submission_pairs_for_students,
    _list_teacher_course_units,
    _list_unit_task_ids,
)


app_diagnostics_router = APIRouter(tags=["App"])


_BOUND_APP_MODULE = _sys.modules.get("backend.web.routes.app")


def _app_helper(name: str, fallback):
    """Resolve patchable helpers through the app facade when available."""

    app_module = _BOUND_APP_MODULE or _sys.modules.get("backend.web.routes.app")
    if app_module is not None and hasattr(app_module, name):
        return getattr(app_module, name)
    return fallback


def _build_diagnostics_course_matrix_rows(
    course_id: str,
    owner_sub: str,
    limit: int,
    offset: int,
    units: list[dict[str, object]],
) -> list[dict[str, object]]:
    members = _app_helper("_list_teacher_course_members", _list_teacher_course_members)(
        course_id,
        owner_sub,
        limit=limit,
        offset=offset,
    )
    task_ids_by_unit = {
        str(unit.get("id") or ""): _app_helper("_list_unit_task_ids", _list_unit_task_ids)(
            str(unit.get("id") or ""),
            owner_sub,
        )
        for unit in units
        if str(unit.get("id") or "")
    }
    all_task_ids = sorted({task_id for unit_task_ids in task_ids_by_unit.values() for task_id in unit_task_ids})
    member_subs = [str(member.get("sub") or "") for member in members if str(member.get("sub") or "")]
    submission_pairs = _app_helper("_list_submission_pairs_for_students", _list_submission_pairs_for_students)(
        course_id,
        owner_sub,
        member_subs,
        all_task_ids,
    )

    rows: list[dict[str, object]] = []
    for member in members:
        student_sub = str(member.get("sub") or "")
        if not student_sub:
            continue
        cells: list[dict[str, object]] = []
        for unit in units:
            unit_id = str(unit.get("id") or "")
            unit_task_ids = task_ids_by_unit.get(unit_id, [])
            submitted_tasks = sum(1 for task_id in unit_task_ids if (student_sub, task_id) in submission_pairs)
            cells.append(
                {
                    "unit_id": unit_id,
                    "submitted_tasks": submitted_tasks,
                    "total_tasks": len(unit_task_ids),
                    "href": f"/live/courses/{course_id}/units/{unit_id}",
                }
            )
        rows.append(
            {
                "student": {
                    "sub": student_sub,
                    "name": str(member.get("name") or student_sub),
                    "href": f"/diagnostics/learners/{student_sub}",
                },
                "cells": cells,
            }
        )
    return rows


def _teacher_course_has_member(course_id: str, owner_sub: str, student_sub: str) -> bool:
    """Compatibility facade for legacy tests; profile pages use the bulk query."""

    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    return bool(repo.course_has_member(course_id, owner_sub, student_sub))


def _build_diagnostics_learner_profile_courses(
    student_sub: str,
    owner_sub: str,
    limit: int,
    offset: int,
) -> list[dict[str, object]]:
    courses: list[dict[str, object]] = []
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    visible_courses = repo.list_active_courses_for_owner_member(
        owner_sub=owner_sub,
        student_sub=student_sub,
        limit=limit,
        offset=offset,
    )

    for course in visible_courses:
        course_id = str(course.get("id") or "")
        if not course_id:
            continue

        units = [
            {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or ""),
                "position": int(item.get("position") or 0),
                "href": f"/diagnostics/courses/{course_id}/units/{item.get('id')}",
            }
            for item in _app_helper("_list_teacher_course_units", _list_teacher_course_units)(course_id, owner_sub)
            if isinstance(item, dict)
        ]
        task_ids_by_unit = {
            str(unit.get("id") or ""): _app_helper("_list_unit_task_ids", _list_unit_task_ids)(
                str(unit.get("id") or ""),
                owner_sub,
            )
            for unit in units
            if str(unit.get("id") or "")
        }
        all_task_ids = sorted({task_id for unit_task_ids in task_ids_by_unit.values() for task_id in unit_task_ids})
        submission_pairs = _app_helper("_list_submission_pairs_for_students", _list_submission_pairs_for_students)(
            course_id,
            owner_sub,
            [student_sub],
            all_task_ids,
        )

        unit_summaries: list[dict[str, object]] = []
        course_submitted_tasks = 0
        course_total_tasks = 0
        for unit in units:
            unit_id = str(unit.get("id") or "")
            unit_task_ids = task_ids_by_unit.get(unit_id, [])
            submitted_tasks = sum(1 for task_id in unit_task_ids if (student_sub, task_id) in submission_pairs)
            total_tasks = len(unit_task_ids)
            course_submitted_tasks += submitted_tasks
            course_total_tasks += total_tasks
            unit_summaries.append(
                {
                    "id": unit_id,
                    "title": str(unit.get("title") or ""),
                    "position": int(unit.get("position") or 0),
                    "href": str(unit.get("href") or ""),
                    "submitted_tasks": submitted_tasks,
                    "total_tasks": total_tasks,
                }
            )

        courses.append(
            {
                "id": course_id,
                "title": str(course.get("title") or ""),
                "href": f"/diagnostics/courses/{course_id}",
                "submitted_tasks": course_submitted_tasks,
                "total_tasks": course_total_tasks,
                "units": unit_summaries,
            }
        )
    return courses


@app_diagnostics_router.get("/api/diagnostics/views/courses/{course_id}/matrix")
async def get_diagnostics_course_matrix(request: Request, course_id: str, limit: str = "25", offset: str = "0"):
    """Return the first course-scoped diagnostics matrix for SvelteKit."""
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())
    pagination = parse_bounded_pagination(
        limit,
        offset,
        default_limit=25,
        maximum_limit=50,
    )
    if pagination is None:
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_pagination"},
            status_code=400,
            headers=_private_headers(),
        )
    page_limit, page_offset = pagination

    owner_sub = str(user.get("sub") or "")
    guard = teaching_guards._guard_course_owner(
        course_id,
        owner_sub,
        repo_provider=teaching_routes._get_current_teaching_repo_for_provider,
    )
    if guard:
        return guard

    course = _app_helper("_get_teacher_course", _get_teacher_course)(course_id, owner_sub)
    if course is None:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    units = [
        {
            "id": str(item.get("id") or ""),
            "title": str(item.get("title") or ""),
            "position": int(item.get("position") or 0),
            "href": f"/live/courses/{course_id}/units/{item.get('id')}",
        }
        for item in _app_helper("_list_teacher_course_units", _list_teacher_course_units)(course_id, owner_sub)
        if isinstance(item, dict)
    ]
    body = {
        "user": _user_payload(user),
        "course": {
            "id": str(_app_helper("_field_value", _field_value)(course, "id") or ""),
            "title": str(_app_helper("_field_value", _field_value)(course, "title") or ""),
            "href": f"/diagnostics/courses/{course_id}",
        },
        "units": units,
        "rows": _app_helper("_build_diagnostics_course_matrix_rows", _build_diagnostics_course_matrix_rows)(
            course_id,
            owner_sub,
            limit=page_limit,
            offset=page_offset,
            units=units,
        ),
    }
    return JSONResponse(body, headers=_private_headers())



@app_diagnostics_router.get("/api/diagnostics/views/learners/{student_sub:path}/profile")
async def get_diagnostics_learner_profile(request: Request, student_sub: str, limit: str = "50", offset: str = "0"):
    """Return the first learner-scoped diagnostics profile for SvelteKit."""
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())
    pagination = parse_bounded_pagination(
        limit,
        offset,
        default_limit=50,
        maximum_limit=50,
    )
    if pagination is None:
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_pagination"},
            status_code=400,
            headers=_private_headers(),
        )
    page_limit, page_offset = pagination

    owner_sub = str(user.get("sub") or "")
    courses = _app_helper(
        "_build_diagnostics_learner_profile_courses",
        _build_diagnostics_learner_profile_courses,
    )(
        student_sub,
        owner_sub,
        limit=page_limit,
        offset=page_offset,
    )
    if not courses:
        if page_offset == 0:
            return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())
        first_visible_page = _app_helper(
            "_build_diagnostics_learner_profile_courses",
            _build_diagnostics_learner_profile_courses,
        )(
            student_sub,
            owner_sub,
            limit=1,
            offset=0,
        )
        if not first_visible_page:
            return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    learner_names = teaching_routes.resolve_student_names([student_sub])
    learner_name = str(learner_names.get(student_sub, student_sub))
    body = {
        "user": _user_payload(user),
        "learner": {
            "sub": student_sub,
            "name": learner_name,
            "href": f"/diagnostics/learners/{student_sub}",
        },
        "summary": {
            "courses_count": len(courses),
            "submitted_tasks": sum(int(course.get("submitted_tasks") or 0) for course in courses),
            "total_tasks": sum(int(course.get("total_tasks") or 0) for course in courses),
        },
        "courses": courses,
    }
    return JSONResponse(body, headers=_private_headers())
