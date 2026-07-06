"""Contracts for keeping Learning modular-unit read queries outside repo_db."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_SOURCE = PROJECT_ROOT / "backend" / "learning" / "repo_db.py"
QUERY_SOURCE = PROJECT_ROOT / "backend" / "learning" / "repo_modular_unit_queries.py"


def test_modular_unit_query_implementations_live_outside_learning_repo_hotspot() -> None:
    repo_db = importlib.import_module("backend.learning.repo_db")
    query_module = importlib.import_module("backend.learning.repo_modular_unit_queries")
    repo_source = REPO_SOURCE.read_text(encoding="utf-8")
    query_source = QUERY_SOURCE.read_text(encoding="utf-8")

    assert "public.get_modular_unit_module_states_for_student" not in repo_source
    assert "public.get_released_sections_for_student_by_unit" not in repo_source
    assert "public.get_released_materials_for_student" not in repo_source
    assert "public.get_released_tasks_for_student" not in repo_source
    assert "def get_modular_unit_graph(" in query_source
    assert "def get_modular_module_content(" in query_source
    assert "def list_released_sections(" in query_source
    assert "def list_released_sections_by_unit(" in query_source
    assert "def is_h5p_content_released_for_student(" in query_source
    assert "def is_modular_section_open_or_done(" in query_source
    assert repo_db._repo_modular_unit_queries is query_module
