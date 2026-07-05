"""
Teaching web adapter -- Filius task marker config.

Intent:
    The FastAPI/Pydantic adapter must preserve `filius: {}` from request
    payloads and serialize Filius tasks with the same mutually-exclusive marker
    shape as Scratch and Calliope.
"""

from __future__ import annotations

import importlib
from pathlib import Path

teaching = importlib.import_module("backend.web.routes.teaching")
payloads = importlib.import_module("backend.web.routes.teaching_payloads")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEACHING_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching.py"
PAYLOADS_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching_payloads.py"


def test_teaching_payload_models_live_outside_teaching_hotspot() -> None:
    """Request payload models should not keep growing the teaching route hotspot."""

    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")
    payload_source = PAYLOADS_SOURCE.read_text(encoding="utf-8")

    assert "class TaskCreatePayload" not in teaching_source
    assert "class TaskCreatePayload" in payload_source
    assert teaching.TaskCreatePayload is payloads.TaskCreatePayload
    assert teaching.AddMember is payloads.AddMember


def test_task_create_payload_accepts_filius_marker_config() -> None:
    payload = teaching.TaskCreatePayload(instruction_md="Analysiere das Netz", filius={})

    assert payload.filius == {}


def test_task_update_payload_preserves_explicit_filius_update() -> None:
    payload = teaching.TaskUpdatePayload(filius={})

    assert payload.model_dump(mode="python", exclude_unset=True) == {"filius": {}}


def test_serialize_task_exposes_only_filius_marker_for_filius_tasks() -> None:
    serialized = teaching._serialize_task(
        {
            "id": "task-1",
            "unit_id": "unit-1",
            "section_id": "section-1",
            "instruction_md": "Analysiere das Netz",
            "criteria": [],
            "position": 1,
            "created_at": "2026-05-07T12:00:00+00:00",
            "updated_at": "2026-05-07T12:00:00+00:00",
            "kind": "filius",
        }
    )

    assert serialized["filius"] == {}
    assert serialized["h5p"] is None
    assert serialized["visual"] is None
    assert serialized["scratch"] is None
    assert serialized["calliope"] is None
