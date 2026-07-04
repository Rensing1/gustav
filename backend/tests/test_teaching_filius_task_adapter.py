"""
Teaching web adapter -- Filius task marker config.

Intent:
    The FastAPI/Pydantic adapter must preserve `filius: {}` from request
    payloads and serialize Filius tasks with the same mutually-exclusive marker
    shape as Scratch and Calliope.
"""

from __future__ import annotations

import importlib

teaching = importlib.import_module("backend.web.routes.teaching")


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
