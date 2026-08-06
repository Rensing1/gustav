"""Teacher course read-model routes for the browser app."""

from __future__ import annotations

import importlib
import sys as _sys
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from backend.web.routes import teaching as teaching_routes
from backend.web.routes import teaching_guards
from backend.web.security.guards import has_any_role, has_role


app_teacher_course_router = APIRouter(tags=["App"])


def _app_module():
    module = _sys.modules.get("backend.web.routes.app")
    if module is None:  # pragma: no cover - defensive import fallback
        module = importlib.import_module("backend.web.routes.app")
    return module


def _current_user(request: Request) -> dict | None:
    return _app_module()._current_user(request)


def _private_headers() -> dict[str, str]:
    return _app_module()._private_headers()


def _user_payload(user: dict) -> dict[str, object]:
    return _app_module()._user_payload(user)


def _count_teacher_course_members(course_id: str, owner_sub: str) -> int:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    page_size = 100
    offset = 0
    total = 0

    while True:
        try:
            page = repo.list_members_for_owner(course_id, owner_sub, limit=page_size, offset=offset)
        except Exception:
            page = repo.list_members(course_id, limit=page_size, offset=offset)
        if not page:
            return total
        total += len(page)
        if len(page) < page_size:
            return total
        offset += page_size


def _list_teacher_course_cards(
    owner_sub: str,
    limit: int,
    offset: int,
    *,
    status: str = "active",
    query: str = "",
    school_year_start: int | None = None,
    subject: str = "",
) -> list[dict[str, object]]:
    app_routes = _app_module()
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    catalog_method = getattr(repo, "list_course_catalog_for_owner", None)
    if callable(catalog_method):
        courses = catalog_method(
            owner_sub=owner_sub,
            status=status,
            query=query,
            school_year_start=school_year_start,
            subject=subject,
            limit=limit,
            offset=offset,
        )
        return [
            {
                **dict(course),
                "href": f"/teaching/courses/{course.get('id')}",
            }
            for course in courses
        ]
    courses = repo.list_courses_for_teacher(teacher_id=owner_sub, limit=limit, offset=offset)

    items: list[dict[str, object]] = []
    for course in courses or []:
        course_id = str(app_routes._field_value(course, "id") or "")
        if not course_id:
            continue

        units = app_routes._list_teacher_course_units(course_id, owner_sub)
        items.append(
            {
                "id": course_id,
                "title": str(app_routes._field_value(course, "title") or ""),
                "href": f"/teaching/courses/{course_id}",
                "members_count": app_routes._count_teacher_course_members(course_id, owner_sub),
                "units_count": len(units),
                "subject": app_routes._field_value(course, "subject"),
                "grade_level": app_routes._field_value(course, "grade_level"),
                "term": app_routes._field_value(course, "term"),
                "school_year_start": app_routes._field_value(course, "school_year_start"),
                "status": str(app_routes._field_value(course, "status") or "active"),
                "metadata_complete": bool(
                    app_routes._field_value(course, "subject")
                    and app_routes._field_value(course, "grade_level")
                    and app_routes._field_value(course, "school_year_start") is not None
                ),
                "archived_at": app_routes._field_value(course, "archived_at"),
            }
        )
    return items


def _list_teacher_course_members(course_id: str, owner_sub: str, limit: int, offset: int) -> list[dict]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        if isinstance(repo, DBTeachingRepo):
            pairs = repo.list_members_for_owner(course_id, owner_sub, limit=limit, offset=offset)
        else:
            pairs = repo.list_members(course_id, limit=limit, offset=offset)
    except Exception:
        pairs = repo.list_members(course_id, limit=limit, offset=offset)

    names = teaching_routes.resolve_student_names([student_sub for student_sub, _joined_at in pairs])
    return [
        {
            "sub": str(student_sub),
            "name": str(names.get(student_sub, student_sub)),
            "href": f"/users/{student_sub}",
            "joined_at": str(joined_at),
        }
        for student_sub, joined_at in pairs
    ]


def _list_teacher_course_members_window(course_id: str, owner_sub: str, limit: int, offset: int) -> list[dict]:
    """Return a larger member window even when the DB helper clamps pages to 50."""

    remaining = max(0, int(limit))
    current_offset = max(0, int(offset))
    members: list[dict] = []
    while remaining > 0:
        page_size = min(50, remaining)
        page = _app_module()._list_teacher_course_members(course_id, owner_sub, limit=page_size, offset=current_offset)
        members.extend(page)
        if len(page) < page_size:
            break
        remaining -= len(page)
        current_offset += len(page)
    return members


def _parse_usage_filter_timestamp(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("invalid_time_filter")
    if parsed.tzinfo is None:
        raise ValueError("invalid_time_filter")
    return parsed.astimezone(timezone.utc)


def _empty_usage_totals() -> dict[str, object]:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "known_events": 0,
        "unknown_events": 0,
        "breakdown": [],
    }


def _build_usage_totals(events: list[dict[str, object]]) -> dict[str, object]:
    totals = _empty_usage_totals()
    breakdown: dict[tuple[str, str, str, str], dict[str, object]] = {}

    for event in events:
        known = bool(event.get("usage_known"))
        if known:
            totals["known_events"] = int(totals["known_events"]) + 1
        else:
            totals["unknown_events"] = int(totals["unknown_events"]) + 1

        for source_key, target_key in (
            ("input_tokens", "input_tokens"),
            ("output_tokens", "output_tokens"),
            ("total_tokens", "total_tokens"),
        ):
            value = event.get(source_key)
            if value is not None:
                totals[target_key] = int(totals[target_key] or 0) + int(value)

        key = (
            str(event.get("model") or "unknown"),
            str(event.get("stage") or ""),
            str(event.get("modality") or ""),
            str(event.get("call_kind") or ""),
        )
        item = breakdown.setdefault(
            key,
            {
                "model": key[0],
                "stage": key[1],
                "modality": key[2],
                "call_kind": key[3],
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "known_events": 0,
                "unknown_events": 0,
            },
        )
        if known:
            item["known_events"] = int(item["known_events"]) + 1
        else:
            item["unknown_events"] = int(item["unknown_events"]) + 1
        for token_key in ("input_tokens", "output_tokens", "total_tokens"):
            value = event.get(token_key)
            if value is not None:
                item[token_key] = int(item[token_key] or 0) + int(value)

    totals["breakdown"] = sorted(
        breakdown.values(),
        key=lambda item: (
            str(item.get("model") or ""),
            str(item.get("stage") or ""),
            str(item.get("modality") or ""),
            str(item.get("call_kind") or ""),
        ),
    )
    return totals


def _list_teacher_course_ai_usage_events(
    *,
    course_id: str,
    owner_sub: str,
    from_at: datetime | None,
    to_at: datetime | None,
    unit_id: str | None,
    task_id: str | None,
    student_sub: str | None,
) -> list[dict[str, object]]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    method = getattr(repo, "list_ai_usage_events_for_owner", None)
    if not callable(method):
        return []
    return list(
        method(
            course_id=course_id,
            owner_sub=owner_sub,
            from_at=from_at,
            to_at=to_at,
            unit_id=unit_id,
            task_id=task_id,
            student_sub=student_sub,
        )
        or []
    )


def _get_teacher_course(course_id: str, owner_sub: str):
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        if isinstance(repo, DBTeachingRepo):
            return repo.get_course_for_owner(course_id, owner_sub)
    except Exception:
        pass
    return repo.get_course(course_id)


@app_teacher_course_router.get("/api/teaching/views/courses")
async def get_teacher_course_list(
    request: Request,
    status: str = "active",
    query: str = "",
    school_year_start: int | None = None,
    subject: str = "",
    limit: int = 25,
    offset: int = 0,
):
    """Return the owner-scoped course overview for the teacher workspace."""

    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

    normalized_status = "archived" if status == "archived" else "active"
    body = {
        "user": _user_payload(user),
        "status": normalized_status,
        "query": str(query or "").strip(),
        "school_year_start": school_year_start,
        "subject": str(subject or "").strip(),
        "courses": _app_module()._list_teacher_course_cards(
            str(user.get("sub") or ""),
            limit=int(limit or 25),
            offset=int(offset or 0),
            status=normalized_status,
            query=str(query or "").strip(),
            school_year_start=school_year_start,
            subject=str(subject or "").strip(),
        ),
    }
    return JSONResponse(body, headers=_private_headers())


@app_teacher_course_router.get("/api/teaching/views/courses/{course_id}/context")
async def get_teacher_course_context(request: Request, course_id: str, limit: int = 25, offset: int = 0):
    """Return the first course-scoped teacher read-model for SvelteKit."""

    app_routes = _app_module()
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

    course = app_routes._get_teacher_course(course_id, owner_sub)
    if course is None:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    units = [
        {
            "id": str(item.get("id") or ""),
            "title": str(item.get("title") or ""),
            "position": int(item.get("position") or 0),
            "href": f"/teaching/units/{item.get('id')}",
        }
        for item in app_routes._list_teacher_course_units(course_id, owner_sub)
        if isinstance(item, dict)
    ]
    members = app_routes._list_teacher_course_members(course_id, owner_sub, limit=int(limit or 25), offset=int(offset or 0))

    body = {
        "user": _user_payload(user),
        "course": {
            "id": str(app_routes._field_value(course, "id") or ""),
            "title": str(app_routes._field_value(course, "title") or ""),
            "href": f"/teaching/courses/{course_id}",
            "members_href": f"/teaching/courses/{course_id}/members",
            "diagnostics_href": f"/diagnostics/courses/{course_id}",
            "members_count": len(members),
            "units_count": len(units),
        },
        "units": units,
        "members": members,
    }
    return JSONResponse(body, headers=_private_headers())


@app_teacher_course_router.get("/api/teaching/views/courses/{course_id}/ai-usage")
async def get_teacher_course_ai_usage(
    request: Request,
    course_id: str,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    unit_id: str | None = None,
    task_id: str | None = None,
    student_sub: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """Return owner-scoped technical AI token counters for one course.

    Why:
        Teachers need a cost-estimation view for GUSTAV's AI processing. The
        response deliberately contains only counters and grouping dimensions,
        never prompts, answers, file names or provider raw payloads.

    Permissions:
        Caller must be a teacher who owns the course. Admins intentionally get
        no cross-course shortcut in v1.
    """

    app_routes = _app_module()
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_role(user, "teacher"):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

    owner_sub = str(user.get("sub") or "")
    guard = teaching_guards._guard_course_owner(
        course_id,
        owner_sub,
        repo_provider=teaching_routes._get_current_teaching_repo_for_provider,
    )
    if guard:
        guard.headers.setdefault("Cache-Control", _private_headers()["Cache-Control"])
        return guard

    try:
        from_at = app_routes._parse_usage_filter_timestamp(from_)
        to_at = app_routes._parse_usage_filter_timestamp(to)
    except ValueError:
        return JSONResponse({"error": "invalid_time_filter"}, status_code=422, headers=_private_headers())
    if from_at is not None and to_at is not None and from_at >= to_at:
        return JSONResponse({"error": "invalid_time_range"}, status_code=422, headers=_private_headers())

    course = app_routes._get_teacher_course(course_id, owner_sub)
    if course is None:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    page_limit = max(1, min(int(limit or 50), 200))
    page_offset = max(0, int(offset or 0))
    members = app_routes._list_teacher_course_members_window(course_id, owner_sub, limit=page_limit, offset=page_offset)
    events = app_routes._list_teacher_course_ai_usage_events(
        course_id=course_id,
        owner_sub=owner_sub,
        from_at=from_at,
        to_at=to_at,
        unit_id=str(unit_id).strip() if unit_id else None,
        task_id=str(task_id).strip() if task_id else None,
        student_sub=str(student_sub).strip() if student_sub else None,
    )

    events_by_student: dict[str, list[dict[str, object]]] = {}
    for event in events:
        key = str(event.get("student_sub") or "")
        if key:
            events_by_student.setdefault(key, []).append(event)

    learners = []
    for member in members:
        sub = str(member.get("sub") or "")
        member_events = events_by_student.get(sub, [])
        learners.append({"student": member, "totals": app_routes._build_usage_totals(member_events)})

    body = {
        "user": _user_payload(user),
        "course": {
            "id": str(app_routes._field_value(course, "id") or ""),
            "title": str(app_routes._field_value(course, "title") or ""),
            "href": f"/teaching/courses/{course_id}",
            "members_href": f"/teaching/courses/{course_id}/members",
            "diagnostics_href": f"/diagnostics/courses/{course_id}",
            "members_count": len(members),
            "units_count": len(app_routes._list_teacher_course_units(course_id, owner_sub)),
        },
        "filters": {
            "from": from_at.isoformat() if from_at else None,
            "to": to_at.isoformat() if to_at else None,
            "unit_id": str(unit_id).strip() if unit_id else None,
            "task_id": str(task_id).strip() if task_id else None,
            "student_sub": str(student_sub).strip() if student_sub else None,
        },
        "totals": app_routes._build_usage_totals(events),
        "learners": learners,
        "pagination": {"limit": page_limit, "offset": page_offset, "count": len(learners)},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return JSONResponse(body, headers=_private_headers())
