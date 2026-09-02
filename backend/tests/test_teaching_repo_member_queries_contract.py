"""Contracts for Teaching DB course-member query helper ownership."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_db.py"
MEMBER_QUERIES_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_member_queries.py"

MEMBER_QUERY_METHODS = (
    "list_courses_for_student",
    "list_active_courses_for_owner_member",
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


def test_owner_member_course_page_is_filtered_and_paginated_in_one_query() -> None:
    source = MEMBER_QUERIES_SOURCE.read_text(encoding="utf-8")
    function_source = source.split("def list_active_courses_for_owner_member(", 1)[1].split(
        "\ndef course_has_member(", 1
    )[0]

    assert "c.teacher_id = %s" in function_source
    assert "c.status = 'active'" in function_source
    assert "m.student_id = %s" in function_source
    assert "m.ended_at is null" in function_source
    assert "limit %s offset %s" in function_source
    assert function_source.count("cur.execute(") == 2  # current subject plus one data query
