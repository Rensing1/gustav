"""Contracts for Teaching DB row mapping helper ownership."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_db.py"
MAPPERS_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_row_mappers.py"


def test_repo_row_mapping_helpers_live_outside_repo_hotspot() -> None:
    """Pure row mapping helpers should not keep growing DBTeachingRepo."""

    repo_db = importlib.import_module("backend.teaching.repo_db")
    mappers = importlib.import_module("backend.teaching.repo_row_mappers")
    repo_source = REPO_SOURCE.read_text(encoding="utf-8")
    mappers_source = MAPPERS_SOURCE.read_text(encoding="utf-8")

    assert "def _material_row_to_dict(" not in repo_source
    assert "def _task_row_to_dict(" not in repo_source
    assert "def _compute_average_score_from_analysis(" not in repo_source
    assert "def material_row_to_dict(" in mappers_source
    assert "def task_row_to_dict(" in mappers_source
    assert "def compute_average_score_from_analysis(" in mappers_source
    assert repo_db._MATERIAL_COLUMNS_SQL == mappers.MATERIAL_COLUMNS_SQL
    assert repo_db._TASK_COLUMNS_SQL == mappers.TASK_COLUMNS_SQL
    assert repo_db._material_row_to_dict is mappers.material_row_to_dict
    assert repo_db._task_row_to_dict is mappers.task_row_to_dict
    assert repo_db._compute_average_score_from_analysis is mappers.compute_average_score_from_analysis
