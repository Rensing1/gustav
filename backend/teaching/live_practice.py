"""Pure classification rules for practice modules in the teacher Live view."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def build_practice_modules(
    *,
    sections: Iterable[dict[str, Any]],
    tasks: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build the ordered practice-module catalog, including empty modules."""
    task_ids_by_module: dict[str, list[str]] = {}
    for task in tasks:
        module_id = str(task.get("module_id") or "")
        if task.get("module_kind") == "practice" and module_id:
            task_ids_by_module.setdefault(module_id, []).append(str(task.get("id") or ""))

    modules: list[dict[str, Any]] = []
    ordered_sections = sorted(
        sections,
        key=lambda section: (int(section.get("position") or 0), str(section.get("id") or "")),
    )
    for section in ordered_sections:
        module_id = str(section.get("module_id") or "")
        if section.get("module_kind") != "practice" or not module_id:
            continue
        modules.append(
            {
                "id": module_id,
                "section_id": str(section.get("id") or ""),
                "title": str(section.get("title") or ""),
                "task_ids": task_ids_by_module.get(module_id, []),
            }
        )
    return modules


def classify_practice_module(
    *,
    access_status: str,
    due: int,
    secure: int,
    partial: int,
    insufficient: int,
    task_count: int,
) -> str:
    """Return the single teacher-facing status for a practice-module cell.

    Why:
        The API, not the browser, owns the status priority. This keeps counts
        and colours consistent for every Live client.

    Permissions:
        None. Authorization and membership checks happen before this pure rule
        receives the already scoped aggregate counts.
    """
    if access_status not in {"open", "done"}:
        return "locked"
    if max(0, due) > 0:
        return "due"
    if max(0, insufficient) > 0:
        return "insufficient"
    if max(0, partial) > 0 or task_count <= 0:
        return "partial"
    if task_count > 0 and secure >= task_count:
        return "secure"
    return "partial"


def build_practice_cells_by_student(
    aggregates: Iterable[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Normalize owner-scoped database rows into public Live practice cells."""
    cells: dict[str, list[dict[str, Any]]] = {}
    ordered = sorted(
        aggregates,
        key=lambda row: (
            str(row.get("student_sub") or ""),
            int(row.get("module_position") or 0),
            str(row.get("module_id") or ""),
        ),
    )
    for row in ordered:
        student_sub = str(row.get("student_sub") or "")
        task_count = int(row.get("task_count") or 0)
        due = int(row.get("due_tasks_count") or 0)
        secure = int(row.get("secure_tasks_count") or 0)
        partial = int(row.get("partial_tasks_count") or 0)
        insufficient = int(row.get("insufficient_tasks_count") or 0)
        cells.setdefault(student_sub, []).append(
            {
                "module_id": str(row.get("module_id") or ""),
                "status": classify_practice_module(
                    access_status=str(row.get("access_status") or "locked"),
                    due=due,
                    secure=secure,
                    partial=partial,
                    insufficient=insufficient,
                    task_count=task_count,
                ),
                "task_count": task_count,
                "due_tasks_count": due,
                "secure_tasks_count": secure,
                "partial_tasks_count": partial,
                "insufficient_tasks_count": insufficient,
                "latest_activity_at": row.get("latest_activity_at"),
                "next_due_at": row.get("next_due_at"),
            }
        )
    return cells
