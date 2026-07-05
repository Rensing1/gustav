"""Contracts for Teaching DB unit-module query helper ownership."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_db.py"
UNIT_MODULE_QUERIES_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_unit_module_queries.py"

UNIT_MODULE_QUERY_METHODS = (
    "list_unit_phases_for_author",
    "create_unit_phase",
    "update_unit_phase_title",
    "reorder_unit_phases_owned",
    "list_unit_modules_for_author",
    "get_unit_module_for_author",
    "list_unit_module_edges_for_author",
    "create_unit_module_for_author",
    "create_unit_module_edge_for_author",
    "delete_unit_module_edge_for_author",
    "reorder_unit_phase_modules_owned",
    "update_unit_module_owned",
    "update_unit_module_title",
    "delete_unit_module_for_author",
    "delete_unit_phase_for_author",
)


def test_unit_module_query_implementations_live_outside_repo_hotspot() -> None:
    """Unit module graph SQL should live in a focused repository module."""

    repo_db = importlib.import_module("backend.teaching.repo_db")
    unit_module_queries = importlib.import_module("backend.teaching.repo_unit_module_queries")
    repo_source = REPO_SOURCE.read_text(encoding="utf-8")
    unit_module_source = UNIT_MODULE_QUERIES_SOURCE.read_text(encoding="utf-8")

    assert hasattr(repo_db, "_repo_unit_module_queries")
    assert repo_db._repo_unit_module_queries is unit_module_queries

    for method_name in UNIT_MODULE_QUERY_METHODS:
        assert f"def {method_name}(" in repo_source
        assert f"repo_unit_module_queries.{method_name}(" in repo_source
        assert f"def {method_name}(" in unit_module_source

    assert "public.unit_modules" not in repo_source
    assert "public.unit_module_edges" not in repo_source
    assert "def _clamp_required_prereq_count_to_incoming(" in unit_module_source
