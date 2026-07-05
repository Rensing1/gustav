"""Contracts for Teaching DB concern-box query helper ownership."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_db.py"
CONCERN_QUERIES_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_concern_box_queries.py"

CONCERN_QUERY_METHODS = (
    "create_concern_box_entry",
    "list_concern_box_entries_for_teacher",
    "archive_concern_box_entry_owned",
    "restore_concern_box_entry_owned",
)


def test_concern_box_query_implementations_live_outside_repo_hotspot() -> None:
    """Concern-box SQL should live in a focused repository module."""

    repo_db = importlib.import_module("backend.teaching.repo_db")
    concern_queries = importlib.import_module("backend.teaching.repo_concern_box_queries")
    repo_source = REPO_SOURCE.read_text(encoding="utf-8")
    concern_source = CONCERN_QUERIES_SOURCE.read_text(encoding="utf-8")

    assert hasattr(repo_db, "_repo_concern_box_queries")
    assert repo_db._repo_concern_box_queries is concern_queries

    for method_name in CONCERN_QUERY_METHODS:
        assert f"def {method_name}(" in repo_source
        assert f"repo_concern_box_queries.{method_name}(" in repo_source
        assert f"def {method_name}(" in concern_source

    assert "public.create_concern_box_entry" not in repo_source
    assert "public.concern_box_entries" not in repo_source
