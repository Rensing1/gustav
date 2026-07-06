"""Live-dashboard Browser-BFF routes.

Why:
    Live read models combine FastAPI handler calls, compact matrix shaping,
    dashboard aggregates, and detail-sheet forwarding. Keeping them together
    outside app.py leaves the app router as a small composition facade.
"""

from __future__ import annotations

import inspect
import json
import sys as _sys

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.web.security.guards import has_any_role
from backend.web.routes import teaching as teaching_routes
from backend.web.routes import teaching_guards
from backend.web.routes.app_session_helpers import (
    current_user as _current_user,
    private_headers as _private_headers,
    user_payload as _user_payload,
)
from backend.web.routes.app_teacher_course_routes import _get_teacher_course
from backend.web.routes.app_teacher_unit_routes import (
    _field_value,
    _find_course_unit,
    _list_teacher_course_units,
)


app_live_router = APIRouter(tags=["App"])


_BOUND_APP_MODULE = _sys.modules.get("backend.web.routes.app")


def _app_helper(name: str, fallback):
    """Resolve patchable helpers through the app facade when available."""

    app_module = _BOUND_APP_MODULE or _sys.modules.get("backend.web.routes.app")
    if app_module is not None and hasattr(app_module, name):
        return getattr(app_module, name)
    return fallback


def _find_course_unit_with_patchable_list(course_id: str, owner_sub: str, unit_id: str) -> dict[str, object] | None:
    """Find a unit through the patchable App facade course-unit helper."""

    direct_finder = _app_helper("_find_course_unit", _find_course_unit)
    app_module = _BOUND_APP_MODULE or _sys.modules.get("backend.web.routes.app")
    if app_module is not None and direct_finder is not _find_course_unit:
        try:
            found = direct_finder(course_id, owner_sub, unit_id)
            if found is not None:
                return found
        except Exception:
            pass

    for item in _app_helper("_list_teacher_course_units", _list_teacher_course_units)(course_id, owner_sub):
        if isinstance(item, dict) and str(item.get("id") or "") == unit_id:
            return item
    return None


def _decode_json_response_body(response: object) -> object:
    body = getattr(response, "body", b"")
    if not body:
        return None
    if isinstance(body, bytes):
        raw = body.decode("utf-8")
    else:
        raw = str(body)
    if not raw:
        return None
    return json.loads(raw)




@app_live_router.get("/api/live/views/courses/{course_id}/units/{unit_id}/matrix")
async def get_live_unit_matrix(request: Request, course_id: str, unit_id: str, limit: int = 100, offset: int = 0):
    """Return the live room matrix read-model for one course-unit pair."""
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

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

    unit = _find_course_unit_with_patchable_list(course_id, owner_sub, unit_id)
    if unit is None:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    summary_result = teaching_routes.get_unit_live_summary(
        request,
        course_id=course_id,
        unit_id=unit_id,
        limit=int(limit or 100),
        offset=int(offset or 0),
    )
    summary_response = await summary_result if inspect.isawaitable(summary_result) else summary_result
    if getattr(summary_response, "status_code", 500) != 200:
        return summary_response

    payload = _decode_json_response_body(summary_response)
    data = payload if isinstance(payload, dict) else {}
    tasks = data.get("tasks") if isinstance(data.get("tasks"), list) else []
    rows_in = data.get("rows") if isinstance(data.get("rows"), list) else []

    rows: list[dict[str, object]] = []
    for row in rows_in:
        if not isinstance(row, dict):
            continue
        student = row.get("student") if isinstance(row.get("student"), dict) else {}
        student_sub = str(student.get("sub") or "")
        student_name = str(student.get("name") or student_sub)
        task_cells: list[dict[str, object]] = []
        for cell in row.get("tasks") or []:
            if not isinstance(cell, dict):
                continue
            task_id = str(cell.get("task_id") or "")
            task_cell = {
                "task_id": task_id,
                "has_submission": bool(cell.get("has_submission")),
                "average_score": cell.get("average_score"),
                "href": (
                    f"/live/courses/{course_id}/units/{unit_id}"
                    f"?student_sub={student_sub}&task_id={task_id}"
                ),
            }
            if cell.get("score_raw") is not None:
                task_cell["score_raw"] = cell.get("score_raw")
            if cell.get("score_max") is not None:
                task_cell["score_max"] = cell.get("score_max")
            if cell.get("h5p_completed") is not None:
                task_cell["h5p_completed"] = cell.get("h5p_completed")
            task_cells.append(task_cell)
        rows.append(
            {
                "student": {
                    "sub": student_sub,
                    "name": student_name,
                    "href": f"/live/courses/{course_id}/units/{unit_id}?student_sub={student_sub}",
                },
                "tasks": task_cells,
            }
        )

    body = {
        "user": _user_payload(user),
        "course": {
            "id": str(_app_helper("_field_value", _field_value)(course, "id") or ""),
            "title": str(_app_helper("_field_value", _field_value)(course, "title") or ""),
            "href": f"/live/courses/{course_id}",
        },
        "unit": {
            "id": str(unit.get("id") or ""),
            "title": str(unit.get("title") or ""),
            "position": int(unit.get("position") or 0),
            "href": f"/live/courses/{course_id}/units/{unit_id}",
        },
        "tasks": tasks,
        "rows": rows,
    }
    return JSONResponse(body, headers=_private_headers())


@app_live_router.get("/api/live/views/courses/{course_id}/units")
async def get_live_course_units(request: Request, course_id: str):
    """Return a lightweight unit list for the `/live` course selection UI."""
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

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
            "href": f"/live?course_id={course_id}&unit_id={item.get('id')}",
        }
        for item in _app_helper("_list_teacher_course_units", _list_teacher_course_units)(course_id, owner_sub)
        if isinstance(item, dict)
    ]

    body = {
        "user": _user_payload(user),
        "course": {
            "id": str(_app_helper("_field_value", _field_value)(course, "id") or ""),
            "title": str(_app_helper("_field_value", _field_value)(course, "title") or ""),
            "href": f"/live?course_id={course_id}",
        },
        "units": units,
    }
    return JSONResponse(body, headers=_private_headers())


def _live_selection_href(course_id: str, unit_id: str, student_sub: str | None = None, task_id: str | None = None) -> str:
    """Build canonical `/live` dashboard links for course/unit/student selections."""
    parts = [f"course_id={course_id}", f"unit_id={unit_id}"]
    if student_sub:
        parts.append(f"student_sub={student_sub}")
    if task_id:
        parts.append(f"task_id={task_id}")
    return "/live?" + "&".join(parts)


def _round_live_average(values: list[float | None]) -> float | None:
    """Return a stable arithmetic mean for compact dashboard KPIs."""
    numbers = [float(value) for value in values if isinstance(value, (int, float))]
    if not numbers:
        return None
    return round(sum(numbers) / len(numbers), 1)


def _live_task_meta_by_id(tasks: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    """Map task ids to lightweight label metadata for dashboard rendering."""
    out: dict[str, dict[str, object]] = {}
    for task in tasks:
        task_id = str(task.get("id") or "")
        position = int(task.get("position") or 0)
        out[task_id] = {
            "task_position": position,
            "task_label": f"{position}. Aufgabe",
        }
    return out


def _live_dashboard_localpart_identifier(*values: object) -> str:
    """Return a stable localpart-style fallback for live dashboard labels."""
    for candidate in values:
        raw = str(candidate or "").strip()
        if not raw:
            continue
        try:
            from backend.identity_access import directory  # type: ignore

            extractor = getattr(directory, "localpart_identifier", None)
            if callable(extractor):
                localpart = str(extractor(raw) or "").strip()
                if localpart:
                    return localpart
        except Exception:
            pass
        normalized = raw.split(":", 1)[1].strip() if raw.startswith("legacy-email:") else raw
        if "@" in normalized:
            localpart = normalized.split("@", 1)[0].strip()
            if localpart:
                return localpart
    return ""


@app_live_router.get("/api/live/views/courses/{course_id}/units/{unit_id}/dashboard")
async def get_live_unit_dashboard(
    request: Request,
    course_id: str,
    unit_id: str,
    student_sub: str | None = None,
    task_id: str | None = None,
):
    """Return a compact dashboard read-model for one live course-unit pair."""
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

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

    unit = _find_course_unit_with_patchable_list(course_id, owner_sub, unit_id)
    if unit is None:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    summary_result = teaching_routes.get_unit_live_summary(
        request,
        course_id=course_id,
        unit_id=unit_id,
        limit=100,
        offset=0,
    )
    summary_response = await summary_result if inspect.isawaitable(summary_result) else summary_result
    if getattr(summary_response, "status_code", 500) != 200:
        return summary_response

    payload = _decode_json_response_body(summary_response)
    data = payload if isinstance(payload, dict) else {}
    tasks = data.get("tasks") if isinstance(data.get("tasks"), list) else []
    rows_in = data.get("rows") if isinstance(data.get("rows"), list) else []
    task_meta = _live_task_meta_by_id([task for task in tasks if isinstance(task, dict)])
    rows: list[dict[str, object]] = []
    selected_student_panel: dict[str, object] | None = None
    row_average_values: list[float | None] = []
    submitted_cells = 0
    total_cells = 0

    for row in rows_in:
        if not isinstance(row, dict):
            continue
        student = row.get("student") if isinstance(row.get("student"), dict) else {}
        current_student_sub = str(student.get("sub") or "")
        student_name = str(
            student.get("name")
            or _live_dashboard_localpart_identifier(current_student_sub)
            or "Unbekannt"
        )
        row_cells = [cell for cell in (row.get("tasks") or []) if isinstance(cell, dict)]
        total_cells += len(row_cells)
        submitted_count = sum(1 for cell in row_cells if bool(cell.get("has_submission")))
        submitted_cells += submitted_count
        progress_percent = int(round((submitted_count / len(row_cells)) * 100)) if row_cells else 0
        average_score = _round_live_average([cell.get("average_score") for cell in row_cells])
        row_average_values.append(average_score)

        latest_submission: dict[str, object] | None = None
        latest_cell: dict[str, object] | None = None
        latest_created_at = ""
        for cell in row_cells:
            if not bool(cell.get("has_submission")):
                continue
            created_at = str(cell.get("created_at") or "")
            if created_at >= latest_created_at:
                latest_created_at = created_at
                latest_cell = cell

        if latest_cell is not None:
            latest_task_id = str(latest_cell.get("task_id") or "")
            meta = task_meta.get(latest_task_id, {"task_position": 0, "task_label": "Aufgabe"})
            latest_submission = {
                "task_id": latest_task_id,
                "task_position": int(meta["task_position"]),
                "task_label": str(meta["task_label"]),
                "created_at": latest_created_at,
                "average_score": latest_cell.get("average_score"),
            }

        row_href = _live_selection_href(course_id, unit_id, current_student_sub)
        row_payload = {
            "student": {
                "sub": current_student_sub,
                "name": student_name,
                "href": row_href,
            },
            "progress_percent": progress_percent,
            "average_score": average_score,
            "latest_submission": latest_submission,
            "href": row_href,
        }
        rows.append(row_payload)

        if student_sub and current_student_sub == student_sub:
            panel_tasks: list[dict[str, object]] = []
            latest_task_id = str(latest_submission.get("task_id") or "") if isinstance(latest_submission, dict) else ""
            for task in [task for task in tasks if isinstance(task, dict)]:
                current_task_id = str(task.get("id") or "")
                meta = task_meta.get(current_task_id, {"task_position": int(task.get("position") or 0), "task_label": "Aufgabe"})
                matching_cell = next((cell for cell in row_cells if str(cell.get("task_id") or "") == current_task_id), {})
                panel_tasks.append(
                    {
                        "task_id": current_task_id,
                        "task_position": int(meta["task_position"]),
                        "task_label": str(meta["task_label"]),
                        "has_submission": bool(matching_cell.get("has_submission")),
                        "average_score": matching_cell.get("average_score"),
                        "is_latest_submission": current_task_id == latest_task_id,
                        "href": _live_selection_href(course_id, unit_id, current_student_sub, current_task_id),
                    }
                )

            selected_task_id = str(task_id or "").strip() or latest_task_id or None

            selected_task_detail = None
            if selected_task_id:
                detail_result = teaching_routes.get_latest_submission_detail(
                    request,
                    course_id=course_id,
                    unit_id=unit_id,
                    task_id=selected_task_id,
                    student_sub=current_student_sub,
                )
                detail_response = await detail_result if inspect.isawaitable(detail_result) else detail_result
                if getattr(detail_response, "status_code", 500) == 200:
                    selected_task_detail = _decode_json_response_body(detail_response)

            selected_student_panel = {
                "student": {
                    "sub": current_student_sub,
                    "name": student_name,
                    "href": row_href,
                },
                "tasks": panel_tasks,
                "selected_task_id": selected_task_id,
                "selected_task_detail": selected_task_detail,
            }

    summary = {
        "learners_count": len(rows),
        "tasks_count": len(tasks),
        "completion_rate_percent": int(round((submitted_cells / total_cells) * 100)) if total_cells else 0,
        "average_score": _round_live_average(row_average_values),
    }

    body = {
        "user": _user_payload(user),
        "course": {
            "id": str(_app_helper("_field_value", _field_value)(course, "id") or ""),
            "title": str(_app_helper("_field_value", _field_value)(course, "title") or ""),
            "href": f"/live?course_id={course_id}",
        },
        "unit": {
            "id": str(unit.get("id") or ""),
            "title": str(unit.get("title") or ""),
            "position": int(unit.get("position") or 0),
            "href": f"/live?course_id={course_id}&unit_id={unit_id}",
        },
        "summary": summary,
        "rows": rows,
        "selected_student_panel": selected_student_panel,
    }
    return JSONResponse(body, headers=_private_headers())


@app_live_router.get("/api/live/views/courses/{course_id}/units/{unit_id}/detail-sheet")
async def get_live_detail_sheet(request: Request, course_id: str, unit_id: str, student_sub: str, task_id: str):
    """Return the live room detail sheet for one student-task selection."""
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

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

    unit = _find_course_unit_with_patchable_list(course_id, owner_sub, unit_id)
    if unit is None:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    detail_result = teaching_routes.get_latest_submission_detail(
        request,
        course_id=course_id,
        unit_id=unit_id,
        task_id=task_id,
        student_sub=student_sub,
    )
    detail_response = await detail_result if inspect.isawaitable(detail_result) else detail_result
    status_code = getattr(detail_response, "status_code", 500)
    if status_code not in (200, 204):
        return detail_response

    submission = _decode_json_response_body(detail_response) if status_code == 200 else None
    names_result = teaching_routes.resolve_live_student_names_by_sub([student_sub])
    learner_names = await names_result if inspect.isawaitable(names_result) else names_result
    learner_name = str(learner_names.get(student_sub, student_sub))

    body = {
        "user": _user_payload(user),
        "course": {
            "id": str(_app_helper("_field_value", _field_value)(course, "id") or ""),
            "title": str(_app_helper("_field_value", _field_value)(course, "title") or ""),
            "href": f"/live/courses/{course_id}",
        },
        "unit": {
            "id": str(unit.get("id") or ""),
            "title": str(unit.get("title") or ""),
            "position": int(unit.get("position") or 0),
            "href": f"/live/courses/{course_id}/units/{unit_id}",
        },
        "student": {
            "sub": student_sub,
            "name": learner_name,
            "href": f"/live/courses/{course_id}/units/{unit_id}?student_sub={student_sub}",
        },
        "task": {
            "id": task_id,
            "href": f"/live/courses/{course_id}/units/{unit_id}?student_sub={student_sub}&task_id={task_id}",
        },
        "submission": submission,
    }
    return JSONResponse(body, headers=_private_headers())
