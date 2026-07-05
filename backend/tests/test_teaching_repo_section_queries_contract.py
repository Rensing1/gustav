"""Contracts for Teaching DB unit-section query helper ownership."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_db.py"
SECTION_QUERIES_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_section_queries.py"

SECTION_QUERY_METHODS = (
    "section_exists_for_author",
    "list_sections_for_author",
    "create_section",
    "update_section_title",
    "delete_section",
    "reorder_unit_sections_owned",
)


def test_section_query_implementations_live_outside_repo_hotspot() -> None:
    """Unit section SQL should live in a focused repository module."""

    repo_db = importlib.import_module("backend.teaching.repo_db")
    section_queries = importlib.import_module("backend.teaching.repo_section_queries")
    repo_source = REPO_SOURCE.read_text(encoding="utf-8")
    section_source = SECTION_QUERIES_SOURCE.read_text(encoding="utf-8")

    assert hasattr(repo_db, "_repo_section_queries")
    assert repo_db._repo_section_queries is section_queries

    for method_name in SECTION_QUERY_METHODS:
        assert f"def {method_name}(" in repo_source
        assert f"repo_section_queries.{method_name}(" in repo_source
        assert f"def {method_name}(" in section_source

    assert "public.unit_sections" not in repo_source
