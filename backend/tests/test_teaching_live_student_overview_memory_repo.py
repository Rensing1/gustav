"""Regression tests for the in-memory student-live overview repo helpers."""

from __future__ import annotations

import importlib

teaching = importlib.import_module("backend.web.routes.teaching")


def test_memory_repo_keeps_section_order_when_course_unit_tasks_are_flattened() -> None:
    """Tasks from earlier sections must stay ahead of later sections.

    Why:
        The in-memory fallback is used in tests and offline development. Its
        course-scoped task ordering should match the DB-backed repo and preserve
        section order before using the task id as a tiebreaker.
    """

    repo = teaching._Repo()  # type: ignore[attr-defined]
    owner_sub = "teacher-memory-live-order"

    course = repo.create_course(
        title="Kurs",
        subject=None,
        grade_level=None,
        term=None,
        teacher_id=owner_sub,
    )
    unit = repo.create_unit(title="Einheit", summary=None, author_id=owner_sub)
    section_a = repo.create_section(unit.id, "Abschnitt A", owner_sub)
    section_b = repo.create_section(unit.id, "Abschnitt B", owner_sub)
    repo.create_course_module_owned(course.id, owner_sub, unit_id=unit.id, context_notes=None)

    task_a = repo.create_task(
        unit.id,
        section_a.id,
        owner_sub,
        instruction_md="### Aufgabe A",
        criteria=["K1"],
    )
    task_b = repo.create_task(
        unit.id,
        section_b.id,
        owner_sub,
        instruction_md="### Aufgabe B",
        criteria=["K1"],
    )

    # Force an inverse lexical order so the regression is deterministic.
    repo.tasks[task_a.id].id = "zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz"
    repo.tasks[task_b.id].id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    tasks = repo.list_tasks_for_course_unit_owner(course.id, unit.id, owner_sub)

    assert [task["instruction_md"] for task in tasks] == ["### Aufgabe A", "### Aufgabe B"]
    assert [task["position"] for task in tasks] == [1, 2]
