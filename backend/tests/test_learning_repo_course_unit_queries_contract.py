"""Contracts for keeping Learning course/unit read queries outside repo_db."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_SOURCE = PROJECT_ROOT / "backend" / "learning" / "repo_db.py"
QUERY_SOURCE = PROJECT_ROOT / "backend" / "learning" / "repo_course_unit_queries.py"


def test_course_unit_query_implementations_live_outside_learning_repo_hotspot() -> None:
    repo_db = importlib.import_module("backend.learning.repo_db")
    query_module = importlib.import_module("backend.learning.repo_course_unit_queries")
    repo_source = REPO_SOURCE.read_text(encoding="utf-8")
    query_source = QUERY_SOURCE.read_text(encoding="utf-8")

    assert "select c.id::text, c.title, c.subject, c.grade_level, c.term" not in repo_source
    assert "join public.course_memberships m" not in repo_source
    assert "select unit_id::text, title, summary, unit_type, module_position" not in repo_source
    assert "def list_courses_for_student(" in query_source
    assert "def list_units_for_student_course(" in query_source
    assert repo_db._repo_course_unit_queries is query_module
