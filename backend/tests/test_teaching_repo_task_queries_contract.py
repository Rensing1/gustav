"""Contracts for Teaching DB task-query helper ownership."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_db.py"
TASK_QUERIES_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_task_queries.py"

TASK_QUERY_METHODS = (
    "list_tasks_for_section_owned",
    "create_task",
    "update_task",
    "delete_task",
    "reorder_section_tasks",
    "list_tasks_for_course_unit_owner",
    "list_tasks_for_course_units_owner",
    "list_latest_submission_aggregates_for_owner",
)


def test_task_query_implementations_live_outside_repo_hotspot() -> None:
    """Task SQL should live in a focused repository module."""

    repo_db = importlib.import_module("backend.teaching.repo_db")
    task_queries = importlib.import_module("backend.teaching.repo_task_queries")
    repo_source = REPO_SOURCE.read_text(encoding="utf-8")
    task_source = TASK_QUERIES_SOURCE.read_text(encoding="utf-8")

    assert hasattr(repo_db, "_repo_task_queries")
    assert repo_db._repo_task_queries is task_queries

    for method_name in TASK_QUERY_METHODS:
        assert f"def {method_name}(" in repo_source
        assert f"repo_task_queries.{method_name}(" in repo_source
        assert f"def {method_name}(" in task_source

    assert "from public.unit_tasks" not in repo_source
    assert "join public.unit_tasks" not in repo_source
    assert "_TASK_COLUMNS_SQL" in task_source
    aggregate_source = task_source.split("def list_latest_submission_aggregates_for_owner(", 1)[1]
    assert "ls.score_raw" in aggregate_source
    assert "ls.score_max" in aggregate_source
