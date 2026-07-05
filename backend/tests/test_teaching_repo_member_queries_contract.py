"""Contracts for Teaching DB course-member query helper ownership."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_db.py"
MEMBER_QUERIES_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_member_queries.py"

MEMBER_QUERY_METHODS = (
    "list_courses_for_student",
    "course_has_member",
    "list_members_for_owner",
    "add_member_owned",
    "remove_member_owned",
    "student_has_course",
    "add_member",
    "list_members",
    "remove_member",
)


def test_member_query_implementations_live_outside_repo_hotspot() -> None:
    """Course membership SQL should live in a focused repository module."""

    repo_db = importlib.import_module("backend.teaching.repo_db")
    member_queries = importlib.import_module("backend.teaching.repo_member_queries")
    repo_source = REPO_SOURCE.read_text(encoding="utf-8")
    member_source = MEMBER_QUERIES_SOURCE.read_text(encoding="utf-8")

    assert hasattr(repo_db, "_repo_member_queries")
    assert repo_db._repo_member_queries is member_queries

    for method_name in MEMBER_QUERY_METHODS:
        assert f"def {method_name}(" in repo_source
        assert f"repo_member_queries.{method_name}(" in repo_source
        assert f"def {method_name}(" in member_source

    assert "public.course_memberships" not in repo_source
    assert "public.get_course_members" not in repo_source
    assert "public.remove_course_membership" not in repo_source
