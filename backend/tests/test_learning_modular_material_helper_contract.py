"""Contracts for modular material helper cleanup in the retired SSR adapter."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_modular_material_file_helper_is_defined_only_once() -> None:
    source = (REPO_ROOT / "backend" / "web" / "routes" / "learning.py").read_text(encoding="utf-8")
    assert source.count("def _resolve_student_modular_material_file_url(") == 1


def test_retired_modular_fragment_does_not_keep_dead_material_preview_fallbacks() -> None:
    source = (REPO_ROOT / "backend" / "web" / "main.py").read_text(encoding="utf-8")

    assert "async def _fetch_student_material_section_map_for_unit(" not in source
    assert "_resolve_student_material_file_url(\n                            student_sub=student_sub,\n                            course_id=str(course_id),\n                            section_id=section_id," not in source
    assert "material_section_map: dict[str, str] | None = None" not in source
