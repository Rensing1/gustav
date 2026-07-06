"""Teacher unit Browser-BFF routes.

Why:
    The app router is the compatibility facade for SvelteKit BFF read models.
    Teacher unit catalog and workspace payloads are a cohesive read surface, so
    their route handlers and small read helpers live together here.
"""

from __future__ import annotations

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


app_teacher_unit_router = APIRouter(tags=["App"])


def _list_teacher_course_units(course_id: str, owner_sub: str) -> list[dict]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    return repo.list_course_units_for_owner(course_id, owner_sub)


def _list_teacher_units(owner_sub: str, limit: int, offset: int) -> list[dict]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    return [
        teaching_routes._serialize_unit(item)  # type: ignore[attr-defined]
        for item in (repo.list_units_for_author(author_id=owner_sub, limit=limit, offset=offset) or [])
    ]


def _list_teacher_courses(owner_sub: str, limit: int, offset: int) -> list[dict[str, str]]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    items = repo.list_courses_for_teacher(teacher_id=owner_sub, limit=limit, offset=offset)
    return [
        {
            "id": str(_field_value(item, "id") or ""),
            "title": str(_field_value(item, "title") or ""),
        }
        for item in (items or [])
        if str(_field_value(item, "id") or "")
    ]


def _list_teacher_unit_sections(unit_id: str, owner_sub: str) -> list[dict]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    return [
        teaching_routes._serialize_section(item)  # type: ignore[attr-defined]
        for item in (repo.list_sections_for_author(unit_id, owner_sub) or [])
    ]


def _list_teacher_section_materials(unit_id: str, section_id: str, owner_sub: str) -> list[dict]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    return [
        teaching_routes._serialize_material(item)  # type: ignore[attr-defined]
        for item in (repo.list_materials_for_section_owned(unit_id, section_id, owner_sub) or [])
    ]


def _list_teacher_section_tasks(unit_id: str, section_id: str, owner_sub: str) -> list[dict]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    return [
        teaching_routes._serialize_task(item)  # type: ignore[attr-defined]
        for item in (repo.list_tasks_for_section_owned(unit_id, section_id, owner_sub) or [])
    ]


def _list_teacher_unit_phases(unit_id: str, owner_sub: str) -> list[dict]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    return [
        teaching_routes._serialize_unit_phase_public(item)  # type: ignore[attr-defined]
        for item in (repo.list_unit_phases_for_author(unit_id, owner_sub) or [])
    ]


def _list_teacher_unit_modules(unit_id: str, owner_sub: str) -> list[dict]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    return [
        dict(item) if isinstance(item, dict) else teaching_routes._serialize_unit_module(item)  # type: ignore[attr-defined]
        for item in (repo.list_unit_modules_for_author(unit_id=unit_id, author_id=owner_sub) or [])
    ]


def _list_teacher_unit_edges(unit_id: str, owner_sub: str) -> list[dict]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    return [
        teaching_routes._serialize_unit_graph_edge(item)  # type: ignore[attr-defined]
        for item in (repo.list_unit_module_edges_for_author(unit_id=unit_id, author_id=owner_sub) or [])
    ]


def _field_value(item: object, key: str) -> object:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _build_teacher_unit_course_refs(owner_sub: str) -> tuple[dict[str, list[dict[str, str]]], list[dict[str, str | None]]]:
    course_refs_by_unit: dict[str, list[dict[str, str]]] = {}
    courses = _list_teacher_courses(owner_sub, limit=200, offset=0)

    for course in courses:
        course_id = str(course.get("id") or "")
        if not course_id:
            continue

        for unit in _list_teacher_course_units(course_id, owner_sub):
            unit_id = str(_field_value(unit, "id") or "")
            if not unit_id:
                continue
            course_refs_by_unit.setdefault(unit_id, []).append(
                {
                    "id": course_id,
                    "title": str(course.get("title") or ""),
                    "href": f"/teaching/courses/{course_id}",
                }
            )

    return course_refs_by_unit, courses


def _list_unit_task_ids(unit_id: str, owner_sub: str) -> list[str]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    task_ids: list[str] = []
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        if isinstance(repo, DBTeachingRepo):
            sections = repo.list_sections_for_author(unit_id, owner_sub)
            for section in sections:
                section_tasks = repo.list_tasks_for_section_owned(unit_id, str(section.get("id") or ""), owner_sub)
                for task in section_tasks:
                    task_id = str(task.get("id") or "")
                    if task_id:
                        task_ids.append(task_id)
            return task_ids
    except Exception:
        pass

    try:
        section_ids = [sid for sid, data in repo.sections.items() if str(getattr(data, "unit_id", "")) == unit_id]
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


@app_teacher_unit_router.get("/api/teaching/views/units/catalog")
async def get_teacher_units_catalog(
    request: Request,
    query: str = "",
    sort: str | None = None,
):
    """Return the teacher units catalog as a structured bestandsliste.

    The payload stays intentionally small and UI-ready. It avoids mixed meta
    strings so the frontend can render a flat table-like inventory with a
    separate course cell and a dedicated title link.
    """
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

    owner_sub = str(user.get("sub") or "")
    course_refs_by_unit, _ = _build_teacher_unit_course_refs(owner_sub)
    units = _list_teacher_units(owner_sub, limit=200, offset=0)

    items: list[dict[str, object]] = []

    for unit in units:
        unit_id = str(unit.get("id") or "")
        refs = course_refs_by_unit.get(unit_id, [])
        sections = _list_teacher_unit_sections(unit_id, owner_sub)
        sections_count = len(sections)
        courses_count = len(refs)
        last_activity = max(
            [str(unit.get("updated_at") or "")]
            + [str(section.get("updated_at") or "") for section in sections]
        )
        haystack = " ".join(
            part.strip().lower()
            for part in (
                str(unit.get("title") or ""),
                str(unit.get("summary") or ""),
            )
            if part
        )

        if courses_count > 0:
            status_label = "Aktiv im Unterricht"
            status_tone = "success"
        elif sections_count == 0:
            status_label = "Entwurf"
            status_tone = "muted"
        else:
            status_label = "In Bearbeitung"
            status_tone = "accent"

        item = {
            "id": unit_id,
            "title": str(unit.get("title") or ""),
            "topic": str(unit.get("summary") or "").strip() or None,
            "updated_at": last_activity,
            "href": f"/teaching/units/{unit_id}",
            "courses_count": courses_count,
            "courses": [
                {
                    "id": str(ref.get("id") or ""),
                    "title": str(ref.get("title") or ""),
                    "href": str(ref.get("href") or ""),
                }
                for ref in refs
                if str(ref.get("id") or "")
            ],
            "status_label": status_label,
            "status_tone": status_tone,
            "searchable": haystack,
        }
        items.append(item)

    query_value = query.strip()
    if query_value:
        needle = query_value.lower()
        items = [item for item in items if needle in str(item["searchable"])]

    active_sort = sort or "updated_desc"
    if active_sort == "title_asc":
        items.sort(key=lambda item: str(item["title"]).lower())
    else:
        items.sort(key=lambda item: str(item["updated_at"]), reverse=True)

    list_items = [
        {
            "id": str(item["id"]),
            "title": str(item["title"]),
            "topic": item["topic"],
            "status_label": str(item["status_label"]),
            "status_tone": str(item["status_tone"]),
            "courses_count": int(item["courses_count"]),
            "courses": item["courses"],
            "updated_at": str(item["updated_at"]),
            "href": str(item["href"]),
        }
        for item in items
    ]

    body = {
        "user": _user_payload(user),
        "query": query_value,
        "sort": active_sort,
        "result_count": len(list_items),
        "items": list_items,
        "create_href": "/teaching/units?create=1",
    }
    return JSONResponse(body, headers=_private_headers())


@app_teacher_unit_router.get("/api/teaching/views/units/{unit_id}/workspace")
async def get_teacher_unit_workspace(
    request: Request,
    unit_id: str,
    section_id: str | None = None,
    phase_id: str | None = None,
    module_id: str | None = None,
    edge_from_module_id: str | None = None,
    edge_to_module_id: str | None = None,
):
    """Return the graph-first teacher unit workspace read-model."""
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())
    if not teaching_routes._is_uuid_like(unit_id):  # type: ignore[attr-defined]
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_unit_id"},
            status_code=400,
            headers=_private_headers(),
        )

    owner_sub = str(user.get("sub") or "")
    guard = teaching_guards._guard_unit_author(
        unit_id,
        owner_sub,
        repo_provider=teaching_routes._get_repo,  # type: ignore[attr-defined]
    )
    if guard:
        return guard

    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    unit = repo.get_unit_for_author(unit_id, owner_sub)
    if not unit:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    serialized_unit = teaching_routes._serialize_unit(unit)  # type: ignore[attr-defined]
    unit_type = str(serialized_unit.get("unit_type") or "linear").strip().lower() or "linear"
    course_refs_by_unit, _courses = _build_teacher_unit_course_refs(owner_sub)
    courses_count = len(course_refs_by_unit.get(unit_id, []))

    counts = {"sections_count": 0, "phases_count": 0, "modules_count": 0, "courses_count": courses_count}
    graph: dict[str, object] = {"kind": unit_type}
    selection: dict[str, object] = {"kind": "none"}

    def _validate_optional_uuid(raw_value: str | None, detail: str) -> str:
        value = str(raw_value or "").strip()
        if value and not teaching_routes._is_uuid_like(value):  # type: ignore[attr-defined]
            raise ValueError(detail)
        return value

    if unit_type == "modular":
        required_methods = (
            "list_unit_phases_for_author",
            "list_unit_modules_for_author",
            "list_unit_module_edges_for_author",
        )
        repo_error = teaching_routes._require_modular_repo_methods(repo, *required_methods)  # type: ignore[attr-defined]
        if repo_error:
            return repo_error

        try:
            selected_phase_id = _validate_optional_uuid(phase_id, "invalid_phase_id")
            selected_module_id = _validate_optional_uuid(module_id, "invalid_module_id")
            edge_source_id = _validate_optional_uuid(edge_from_module_id, "invalid_edge_from_module_id")
            edge_target_id = _validate_optional_uuid(edge_to_module_id, "invalid_edge_to_module_id")
        except ValueError as exc:
            return JSONResponse(
                {"error": "bad_request", "detail": str(exc)},
                status_code=400,
                headers=_private_headers(),
            )

        phases = _list_teacher_unit_phases(unit_id, owner_sub)
        modules = _list_teacher_unit_modules(unit_id, owner_sub)
        edges = _list_teacher_unit_edges(unit_id, owner_sub)

        module_items: list[dict[str, object]] = []
        modules_by_id: dict[str, dict[str, object]] = {}
        phase_items: list[dict[str, object]] = []
        for module in modules:
            section_id = str(module.get("section_id") or "")
            materials_count = 0
            tasks_count = 0
            if section_id:
                materials_count = len(_list_teacher_section_materials(unit_id, section_id, owner_sub))
                tasks_count = len(_list_teacher_section_tasks(unit_id, section_id, owner_sub))
            item = {
                "id": str(module.get("id") or ""),
                "title": str(module.get("title") or ""),
                "phase_id": str(module.get("phase_id") or ""),
                "position_in_phase": int(module.get("position_in_phase") or 0),
                "required_prereq_count": int(module.get("required_prereq_count") or 0),
                "materials_count": materials_count,
                "tasks_count": tasks_count,
                "editor_href": f"/teaching/units/{unit_id}/nodes/{str(module.get('id') or '')}",
                "section_id": section_id or None,
            }
            module_items.append(item)
            if item["id"]:
                modules_by_id[str(item["id"])] = item

        for phase in phases:
            phase_items.append(
                {
                    "id": str(phase.get("id") or ""),
                    "title": str(phase.get("title") or ""),
                    "position": int(phase.get("position") or 0),
                    "modules": [
                        item
                        for item in module_items
                        if str(item.get("phase_id") or "") == str(phase.get("id") or "")
                    ],
                }
            )

        counts = {
            "sections_count": 0,
            "phases_count": len(phases),
            "modules_count": len(module_items),
            "courses_count": courses_count,
        }

        if not selected_module_id and module_items:
            selected_module_id = str(module_items[0].get("id") or "")
        selected_module = modules_by_id.get(selected_module_id or "")
        selected_phase = next(
            (phase for phase in phases if str(phase.get("id") or "") == (selected_phase_id or "")),
            None,
        )
        selected_edge = None
        if edge_source_id and edge_target_id:
            source_title = str((modules_by_id.get(edge_source_id or "") or {}).get("title") or "")
            target_title = str((modules_by_id.get(edge_target_id or "") or {}).get("title") or "")
            selected_edge = {
                "from_id": edge_source_id,
                "to_id": edge_target_id,
                "from_title": source_title,
                "to_title": target_title,
                "exists": any(
                    str(edge.get("from") or "") == edge_source_id and str(edge.get("to") or "") == edge_target_id
                    for edge in edges
                ),
            }

        graph = {
            "kind": "modular",
            "create_phase_href": f"/teaching/units/{unit_id}?create-phase=1",
            "create_module_href": f"/teaching/units/{unit_id}?create-module=1",
            "phases": phase_items,
            "edges": edges,
        }
        if selected_edge:
            selection = {"kind": "edge", "edge": selected_edge}
        elif selected_module:
            selection = {"kind": "module", "module": selected_module}
        elif selected_phase:
            selection = {
                "kind": "phase",
                "phase": {
                    "id": str((selected_phase or {}).get("id") or ""),
                    "title": str((selected_phase or {}).get("title") or ""),
                    "position": int((selected_phase or {}).get("position") or 0),
                },
            }
    else:
        try:
            selected_section_id = _validate_optional_uuid(section_id, "invalid_section_id")
        except ValueError as exc:
            return JSONResponse(
                {"error": "bad_request", "detail": str(exc)},
                status_code=400,
                headers=_private_headers(),
            )

        sections = _list_teacher_unit_sections(unit_id, owner_sub)
        section_items: list[dict[str, object]] = []
        for section in sections:
            current_section_id = str(section.get("id") or "")
            section_items.append(
                {
                    "id": current_section_id,
                    "title": str(section.get("title") or ""),
                    "position": int(section.get("position") or 0),
                    "materials_count": len(_list_teacher_section_materials(unit_id, current_section_id, owner_sub)),
                    "tasks_count": len(_list_teacher_section_tasks(unit_id, current_section_id, owner_sub)),
                    "editor_href": f"/teaching/units/{unit_id}/nodes/{current_section_id}",
                }
            )

        counts = {
            "sections_count": len(section_items),
            "phases_count": 0,
            "modules_count": 0,
            "courses_count": courses_count,
        }

        if not selected_section_id and section_items:
            selected_section_id = str(section_items[0].get("id") or "")

        selected_structure_section = next(
            (section for section in section_items if str(section.get("id") or "") == (selected_section_id or "")),
            None,
        )
        graph = {
            "kind": "linear",
            "create_section_href": f"/teaching/units/{unit_id}?create-section=1",
            "nodes": section_items,
        }
        if selected_structure_section:
            selection = {
                "kind": "section",
                "section": {
                    "id": str(selected_structure_section.get("id") or ""),
                    "title": str(selected_structure_section.get("title") or ""),
                    "position": int(selected_structure_section.get("position") or 0),
                    "editor_href": str(selected_structure_section.get("editor_href") or ""),
                },
            }

    body = {
        "user": _user_payload(user),
        "unit": {
            "id": str(serialized_unit.get("id") or ""),
            "title": str(serialized_unit.get("title") or ""),
            "summary": serialized_unit.get("summary"),
            "unit_type": unit_type,
            "edit_href": f"/teaching/units/{unit_id}?edit=1",
        },
        "counts": counts,
        "graph": graph,
        "selection": selection,
    }
    return JSONResponse(body, headers=_private_headers())


