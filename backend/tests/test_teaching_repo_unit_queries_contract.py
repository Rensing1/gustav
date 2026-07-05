"""Contracts for Teaching DB unit query helper ownership."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_db.py"
UNIT_QUERIES_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_unit_queries.py"

UNIT_QUERY_METHODS = (
    "list_units_for_author",
    "create_unit",
    "update_unit_owned",
    "get_unit_for_author",
    "delete_unit_owned",
    "unit_exists_for_author",
    "unit_exists",
)


def test_unit_query_implementations_live_outside_repo_hotspot() -> None:
    """Unit SQL should live in a focused repository module."""

    repo_db = importlib.import_module("backend.teaching.repo_db")
    unit_queries = importlib.import_module("backend.teaching.repo_unit_queries")
    repo_source = REPO_SOURCE.read_text(encoding="utf-8")
    unit_source = UNIT_QUERIES_SOURCE.read_text(encoding="utf-8")

    assert hasattr(repo_db, "_repo_unit_queries")
    assert repo_db._repo_unit_queries is unit_queries

    for method_name in UNIT_QUERY_METHODS:
        assert f"def {method_name}(" in repo_source
        assert f"repo_unit_queries.{method_name}(" in repo_source
        assert f"def {method_name}(" in unit_source

    assert "public.units" not in repo_source
    assert "public.unit_exists" not in repo_source
