"""Contracts for Teaching DB AI-usage query helper ownership."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_db.py"
AI_USAGE_QUERIES_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_ai_usage_queries.py"


def test_ai_usage_query_implementation_lives_outside_repo_hotspot() -> None:
    """AI usage SQL should live in a focused repository module."""

    repo_db = importlib.import_module("backend.teaching.repo_db")
    ai_usage_queries = importlib.import_module("backend.teaching.repo_ai_usage_queries")
    repo_source = REPO_SOURCE.read_text(encoding="utf-8")
    ai_usage_source = AI_USAGE_QUERIES_SOURCE.read_text(encoding="utf-8")

    assert hasattr(repo_db, "_repo_ai_usage_queries")
    assert repo_db._repo_ai_usage_queries is ai_usage_queries
    assert "def list_ai_usage_events_for_owner(" in repo_source
    assert "repo_ai_usage_queries.list_ai_usage_events_for_owner(" in repo_source
    assert "def list_ai_usage_events_for_owner(" in ai_usage_source
    assert "public.ai_usage_events" not in repo_source


def test_ai_usage_query_unifies_submission_and_student_dialog_usage_in_sql() -> None:
    """The read model should aggregate both event sources before returning rows."""

    source = AI_USAGE_QUERIES_SOURCE.read_text(encoding="utf-8").lower()

    assert "public.ai_usage_events" in source
    assert "public.dialog_ai_usage_events" in source
    assert "union all" in source
    assert "actor_role = 'student'" in source
    assert "dialog_generation" in source
    assert "group by" in source
