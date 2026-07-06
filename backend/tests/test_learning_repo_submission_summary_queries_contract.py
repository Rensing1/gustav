"""Contracts for keeping Learning task-submission summaries outside repo_db."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_SOURCE = PROJECT_ROOT / "backend" / "learning" / "repo_db.py"
QUERY_SOURCE = PROJECT_ROOT / "backend" / "learning" / "repo_submission_summary_queries.py"


def test_submission_summary_query_lives_outside_learning_repo_hotspot() -> None:
    repo_db = importlib.import_module("backend.learning.repo_db")
    query_module = importlib.import_module("backend.learning.repo_submission_summary_queries")
    repo_source = REPO_SOURCE.read_text(encoding="utf-8")
    query_source = QUERY_SOURCE.read_text(encoding="utf-8")

    assert "with latest as (" not in repo_source
    assert "def task_submission_summary_map(" in query_source
    assert repo_db._repo_submission_summary_queries is query_module
