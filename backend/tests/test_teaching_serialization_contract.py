"""Contracts for Teaching response serializer ownership."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEACHING_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching.py"


def test_core_response_serializers_live_outside_teaching_router() -> None:
    """Teaching response shaping belongs in the serialization helper module."""

    serializers = importlib.import_module("backend.web.routes.teaching_serialization")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")

    expected = (
        "_serialize_course",
        "_serialize_unit",
        "_serialize_module",
        "_serialize_section",
        "_serialize_material",
        "_serialize_unit_phase",
        "_serialize_unit_phase_public",
        "_serialize_unit_module",
        "_serialize_unit_graph_edge",
    )
    for name in expected:
        assert hasattr(serializers, name)
        assert f"def {name}" not in teaching_source

    assert serializers._serialize_unit_phase_public(  # type: ignore[attr-defined]
        {"id": "phase-1", "unit_id": "unit-1", "title": "Phase", "position": 2, "created_at": "hidden"}
    ) == {"id": "phase-1", "unit_id": "unit-1", "title": "Phase", "position": 2}
    assert serializers._serialize_unit_module(  # type: ignore[attr-defined]
        SimpleNamespace(
            id="module-1",
            unit_id="unit-1",
            phase_id="phase-1",
            title="Modul",
            position_in_phase=1,
            required_prereq_count=0,
            section_id="hidden",
        )
    ) == {
        "id": "module-1",
        "unit_id": "unit-1",
        "phase_id": "phase-1",
        "title": "Modul",
        "position_in_phase": 1,
        "required_prereq_count": 0,
    }
    assert serializers._serialize_unit_graph_edge(  # type: ignore[attr-defined]
        {"from_module_id": "module-1", "to_module_id": "module-2"}
    ) == {"from": "module-1", "to": "module-2"}
    assert serializers._serialize_course(  # type: ignore[attr-defined]
        SimpleNamespace(id="course-1", title="Kurs", subject="Informatik", grade_level="10", term="2026", teacher_id="teacher-1")
    ) == {
        "id": "course-1",
        "title": "Kurs",
        "subject": "Informatik",
        "grade_level": "10",
        "term": "2026",
        "teacher_id": "teacher-1",
        "created_at": None,
        "updated_at": None,
    }
    assert serializers._serialize_material(  # type: ignore[attr-defined]
        {"id": "material-1", "unit_id": "unit-1", "title": "Material"}
    ) == {"id": "material-1", "unit_id": "unit-1", "title": "Material"}
