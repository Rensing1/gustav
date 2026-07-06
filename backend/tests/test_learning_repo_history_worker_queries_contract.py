"""Contracts for keeping Learning history/worker queries outside repo_db."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_SOURCE = PROJECT_ROOT / "backend" / "learning" / "repo_db.py"
QUERY_SOURCE = PROJECT_ROOT / "backend" / "learning" / "repo_history_worker_queries.py"


def test_history_and_worker_queries_live_outside_learning_repo_hotspot() -> None:
    repo_db = importlib.import_module("backend.learning.repo_db")
    query_module = importlib.import_module("backend.learning.repo_history_worker_queries")
    repo_source = REPO_SOURCE.read_text(encoding="utf-8")
    query_source = QUERY_SOURCE.read_text(encoding="utf-8")

    assert "def list_submissions(" in query_source
    assert "def get_task_kind_for_student(" in query_source
    assert "def resolve_queue_table(" in query_source
    assert "def mark_extracted(" in query_source
    assert "repo," in query_source
    assert "repo_history_worker_queries.list_submissions(" in repo_source
    assert "repo_history_worker_queries.get_task_kind_for_student(" in repo_source
    assert "repo_history_worker_queries.resolve_queue_table(" in repo_source
    assert "repo_history_worker_queries.mark_extracted(" in repo_source
    assert "from public.learning_submissions" not in repo_source
    assert "update public.learning_submissions" not in repo_source
    assert "to_regclass('public.learning_submission_jobs')" not in repo_source
    assert repo_db._repo_history_worker_queries is query_module
