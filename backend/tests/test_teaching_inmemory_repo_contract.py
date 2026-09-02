"""Contracts for the Teaching in-memory fallback repository."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEACHING_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching.py"
REPO_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching_inmemory_repo.py"


def test_inmemory_repo_lives_outside_teaching_hotspot() -> None:
    """The fallback repository should not keep growing the Teaching route hotspot."""

    teaching = importlib.import_module("backend.web.routes.teaching")
    repo_module = importlib.import_module("backend.web.routes.teaching_inmemory_repo")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")
    repo_source = REPO_SOURCE.read_text(encoding="utf-8")

    assert "class _Repo" not in teaching_source
    assert "class InMemoryTeachingRepo" in repo_source
    assert teaching._Repo is repo_module.InMemoryTeachingRepo
    assert teaching.Course is repo_module.Course
    assert teaching.TaskData is repo_module.TaskData


def test_inmemory_repo_keeps_course_and_unit_fallback_behavior() -> None:
    repo_module = importlib.import_module("backend.web.routes.teaching_inmemory_repo")
    repo = repo_module.InMemoryTeachingRepo()

    course = repo.create_course(
        title="  Mathematik 7a  ",
        subject=None,
        grade_level=None,
        term=None,
        teacher_id="teacher-1",
    )
    unit = repo.create_unit(title="  Lineare Funktionen  ", summary="", author_id="teacher-1")

    assert course.title == "Mathematik 7a"
    assert repo.list_courses_for_teacher(teacher_id="teacher-1", limit=20, offset=0) == [course]
    assert unit.title == "Lineare Funktionen"
    assert unit.summary is None
    assert repo.list_units_for_author(author_id="teacher-1", limit=20, offset=0) == [unit]


def test_inmemory_repo_pages_only_active_owner_courses_with_current_membership() -> None:
    repo_module = importlib.import_module("backend.web.routes.teaching_inmemory_repo")
    repo = repo_module.InMemoryTeachingRepo()
    visible = repo.create_course(
        title="Sichtbar",
        subject=None,
        grade_level=None,
        term=None,
        teacher_id="teacher-1",
    )
    foreign = repo.create_course(
        title="Fremd",
        subject=None,
        grade_level=None,
        term=None,
        teacher_id="teacher-2",
    )
    repo.members[visible.id]["student-1"] = "2026-09-01T08:00:00+00:00"
    repo.members[foreign.id]["student-1"] = "2026-09-01T08:00:00+00:00"

    assert repo.list_active_courses_for_owner_member(
        owner_sub="teacher-1",
        student_sub="student-1",
        limit=10,
        offset=0,
    ) == [{"id": visible.id, "title": "Sichtbar"}]
