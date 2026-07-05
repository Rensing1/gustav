"""Contracts for Teaching DB course-module query helper ownership."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_db.py"
COURSE_MODULE_QUERIES_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_course_module_queries.py"

COURSE_MODULE_QUERY_METHODS = (
    "list_course_modules_for_owner",
    "list_course_units_for_owner",
    "create_course_module_owned",
    "reorder_course_modules_owned",
    "delete_course_module_owned",
    "set_module_section_visibility",
    "list_module_section_releases_owned",
)


def test_course_module_query_implementations_live_outside_repo_hotspot() -> None:
    """Course module SQL should live in a focused repository module."""

    repo_db = importlib.import_module("backend.teaching.repo_db")
    course_module_queries = importlib.import_module("backend.teaching.repo_course_module_queries")
    repo_source = REPO_SOURCE.read_text(encoding="utf-8")
    course_module_source = COURSE_MODULE_QUERIES_SOURCE.read_text(encoding="utf-8")

    assert hasattr(repo_db, "_repo_course_module_queries")
    assert repo_db._repo_course_module_queries is course_module_queries

    for method_name in COURSE_MODULE_QUERY_METHODS:
        assert f"def {method_name}(" in repo_source
        assert f"repo_course_module_queries.{method_name}(" in repo_source
        assert f"def {method_name}(" in course_module_source

    assert "public.course_modules" not in repo_source
    assert "public.module_section_releases" not in repo_source
