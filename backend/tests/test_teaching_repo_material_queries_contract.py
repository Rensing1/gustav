"""Contracts for Teaching DB material-query helper ownership."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_db.py"
MATERIAL_QUERIES_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_material_queries.py"

MATERIAL_QUERY_METHODS = (
    "list_materials_for_section_owned",
    "create_markdown_material",
    "get_material_owned",
    "update_material",
    "delete_material",
    "create_file_upload_intent",
    "get_upload_intent_owned",
    "finalize_upload_intent_create_material",
    "reorder_section_materials",
)


def test_material_query_implementations_live_outside_repo_hotspot() -> None:
    """Material and upload-intent SQL should live in a focused repository module."""

    repo_db = importlib.import_module("backend.teaching.repo_db")
    material_queries = importlib.import_module("backend.teaching.repo_material_queries")
    repo_source = REPO_SOURCE.read_text(encoding="utf-8")
    material_source = MATERIAL_QUERIES_SOURCE.read_text(encoding="utf-8")

    assert hasattr(repo_db, "_repo_material_queries")
    assert repo_db._repo_material_queries is material_queries

    for method_name in MATERIAL_QUERY_METHODS:
        assert f"def {method_name}(" in repo_source
        assert f"repo_material_queries.{method_name}(" in repo_source
        assert f"def {method_name}(" in material_source

    assert "from public.unit_materials" not in repo_source
    assert "from public.upload_intents" not in repo_source
    assert "_MATERIAL_COLUMNS_SQL" in material_source
