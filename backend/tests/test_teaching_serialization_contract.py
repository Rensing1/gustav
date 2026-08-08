"""Contracts for Teaching response serializer ownership."""

from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone
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
        "_build_live_summary_rows",
        "_build_live_delta_cells",
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
        "module_kind": "learning",
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
            "school_year_start": None,
            "status": "active",
            "metadata_complete": False,
            "archived_at": None,
            "teacher_id": "teacher-1",
        "created_at": None,
        "updated_at": None,
    }
    assert serializers._serialize_material(  # type: ignore[attr-defined]
        {"id": "material-1", "unit_id": "unit-1", "title": "Material"}
    ) == {"id": "material-1", "unit_id": "unit-1", "title": "Material"}
    assert serializers._build_live_summary_rows(  # type: ignore[attr-defined]
        members=["student-1", "student-2"],
        names={"student-1": "Anna"},
        tasks=[{"id": "task-1", "kind": "h5p"}, {"id": "task-2", "kind": "text"}],
        has_map={("student-1", "task-1"), ("student-1", "task-2")},
        avg_map={("student-1", "task-1"): 0.8, ("student-1", "task-2"): 0.4},
        created_at_map={("student-1", "task-1"): "2026-01-01T00:00:00Z"},
        score_map={("student-1", "task-1"): (10, 12)},
        h5p_map={("student-1", "task-1"): True},
    ) == [
        {
            "student": {"sub": "student-1", "name": "Anna"},
            "tasks": [
                {
                    "task_id": "task-1",
                    "has_submission": True,
                    "average_score": 0.8,
                    "created_at": "2026-01-01T00:00:00Z",
                    "score_raw": 10,
                    "score_max": 12,
                    "h5p_completed": True,
                },
                {
                    "task_id": "task-2",
                    "has_submission": True,
                    "average_score": 0.4,
                    "created_at": None,
                },
            ],
        },
        {
            "student": {"sub": "student-2", "name": "Unbekannt"},
            "tasks": [
                {
                    "task_id": "task-1",
                    "has_submission": False,
                    "average_score": None,
                    "created_at": None,
                },
                {
                    "task_id": "task-2",
                    "has_submission": False,
                    "average_score": None,
                    "created_at": None,
                },
            ],
        },
    ]


def test_latest_submission_response_shaping_lives_outside_teaching_router() -> None:
    """Latest-submission response shaping should be reusable outside the route."""

    serializers = importlib.import_module("backend.web.routes.teaching_serialization")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")

    expected = ("_normalise_analysis_json", "_build_latest_submission_payload")
    for name in expected:
        assert hasattr(serializers, name)
        assert f"def {name}" not in teaching_source

    assert serializers._normalise_analysis_json(  # type: ignore[attr-defined]
        {"summary": "Gut", "criteria": [{"title": "Korrektheit", "comment": "Passt", "score": "11"}]}
    ) == {
        "schema": "criteria.v2",
        "criteria_results": [
            {"criterion": "Korrektheit", "explanation_md": "Passt", "score": 10},
        ],
    }

    def file_href(**kwargs: str) -> str:
        return f"/download/{kwargs['course_id']}/{kwargs['unit_id']}/{kwargs['task_id']}/{kwargs['student_sub']}"

    payload = serializers._build_latest_submission_payload(  # type: ignore[attr-defined]
        course_id="course-1",
        unit_id="unit-1",
        file_href_builder=file_href,
        sid="submission-1",
        tid="task-1",
        ssub="student-1",
        instruction_md="Bearbeite die Aufgabe.",
        created_at=datetime(2026, 7, 4, 12, 0, tzinfo=timezone.utc),
        completed_at=None,
        kind="file",
        text_body="",
        mime_type="application/pdf",
        size_bytes="42",
        storage_key="submissions/file.pdf",
        analysis_json={"criteria_results": [{"criterion": "Form"}]},
        include_files=True,
    )

    assert payload["kind"] == "pdf"
    assert payload["files"] == [
        {
            "mime": "application/pdf",
            "size": 42,
            "url": "/download/course-1/unit-1/task-1/student-1",
        }
    ]
    assert payload["analysis_json"] == {
        "schema": "criteria.v2",
        "criteria_results": [{"criterion": "Form"}],
    }


def test_live_delta_serializer_shapes_change_cells() -> None:
    serializers = importlib.import_module("backend.web.routes.teaching_serialization")
    now = datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc)

    cells = serializers._build_live_delta_cells(  # type: ignore[attr-defined]
        helper_rows=[
            {
                "student_sub": "student-1",
                "task_id": "task-1",
                "submission_id": "sub-1",
                "score_raw": 10,
                "score_max": 12,
                "created_at_iso": now.isoformat().replace("+00:00", "Z"),
                "h5p_completed": True,
            }
        ],
        latest_state_by_task={},
        avg_by_id={"sub-1": 0.9},
        latest_changed_by_pair={("student-1", "task-1"): now},
        original_updated_dt=now - timedelta(seconds=2),
        timestamp_provider=lambda: now,
        debug=False,
        epsilon_seconds=1,
    )

    assert len(cells) == 1
    assert cells[0]["student_sub"] == "student-1"
    assert cells[0]["task_id"] == "task-1"
    assert cells[0]["has_submission"] is True
    assert cells[0]["average_score"] == 0.9
