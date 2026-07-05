"""Contracts for Teaching DB live-query helper ownership."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_db.py"
LIVE_QUERIES_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_live_queries.py"

LIVE_QUERY_METHODS = (
    "list_unit_latest_submission_aggregates_for_owner",
    "list_unit_live_helper_rows",
    "list_unit_live_submission_state_by_task",
    "list_unit_live_average_scores_by_submission_id",
    "list_unit_live_summary_fallback_rows",
    "list_unit_live_task_ids_for_student",
    "list_unit_live_latest_changed_at_by_pairs",
    "list_unit_live_delta_fallback_rows",
    "get_statement_timestamp",
)


def test_live_query_implementations_live_outside_repo_hotspot() -> None:
    """Live dashboard SQL should live in a focused module, not in DBTeachingRepo."""

    repo_db = importlib.import_module("backend.teaching.repo_db")
    live_queries = importlib.import_module("backend.teaching.repo_live_queries")
    repo_source = REPO_SOURCE.read_text(encoding="utf-8")
    live_source = LIVE_QUERIES_SOURCE.read_text(encoding="utf-8")

    assert hasattr(repo_db, "_repo_live_queries")
    assert repo_db._repo_live_queries is live_queries

    for method_name in LIVE_QUERY_METHODS:
        assert f"def {method_name}(" in repo_source
        assert f"repo_live_queries.{method_name}(" in repo_source
        assert f"def {method_name}(" in live_source

    assert "from public.get_unit_latest_submission_aggregates_for_owner(" not in repo_source
    assert "from public.get_unit_latest_submissions_for_owner(" not in repo_source
    assert "list_unit_live_delta_fallback_rows" in live_source
