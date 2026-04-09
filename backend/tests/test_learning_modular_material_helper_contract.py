"""Contracts for modular material helper definitions in the learning adapter."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_modular_material_file_helper_is_defined_only_once() -> None:
    source = (REPO_ROOT / "backend" / "web" / "routes" / "learning.py").read_text(encoding="utf-8")
    assert source.count("def _resolve_student_modular_material_file_url(") == 1
