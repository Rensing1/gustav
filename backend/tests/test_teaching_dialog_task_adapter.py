"""Contract tests for the Teaching HTTP and persistence dialog adapters."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from backend.teaching.repo_row_mappers import task_row_to_dict
from backend.teaching.repo_task_queries import _dialog_config_row_to_dict

_payloads = importlib.import_module("backend.web.routes.teaching_payloads")
_serialization = importlib.import_module("backend.web.routes.teaching_serialization")
_routes = importlib.import_module("backend.web.routes.teaching_unit_tasks")
TaskCreatePayload = _payloads.TaskCreatePayload
TaskUpdatePayload = _payloads.TaskUpdatePayload
_serialize_task = _serialization._serialize_task


DIALOG = {
    "partner_name": "Sokrates",
    "partner_description_md": "Ein neugieriger Gesprächspartner.",
    "role_md": "Frage nach und gib die Lösung nicht vor.",
    "learning_goal_md": "Begründe eine Position.",
    "opening_message_md": "Welche Position vertrittst du?",
    "response_mode": "hybrid",
    "max_rounds": 8,
    "closing_prompt_md": "Fasse dein Ergebnis zusammen.",
}


def _task_row(kind: str = "dialog") -> tuple[object, ...]:
    return (
        "task-1",
        "unit-1",
        "section-1",
        "Bearbeite die Aufgabe",
        ["Begründung"],
        "Interner Kontext",
        None,
        2,
        1,
        "2026-08-01T09:00:00+00:00",
        "2026-08-01T09:00:00+00:00",
        kind,
        None,
        {},
    )


def test_task_payloads_accept_dialog_config() -> None:
    created = TaskCreatePayload(instruction_md="Diskutiere", dialog=DIALOG)
    updated = TaskUpdatePayload(dialog=DIALOG)

    assert created.dialog == DIALOG
    assert updated.model_dump(exclude_unset=True)["dialog"] == DIALOG


def test_task_row_mapper_initializes_dialog_as_none() -> None:
    task = task_row_to_dict(_task_row("native"))

    assert task["dialog"] is None


def test_dialog_config_row_mapper_omits_task_id_and_metadata() -> None:
    row = (
        "task-1",
        DIALOG["partner_name"],
        DIALOG["partner_description_md"],
        DIALOG["role_md"],
        DIALOG["learning_goal_md"],
        DIALOG["opening_message_md"],
        DIALOG["response_mode"],
        DIALOG["max_rounds"],
        DIALOG["closing_prompt_md"],
    )

    assert _dialog_config_row_to_dict(row) == DIALOG


def test_teaching_serializer_exposes_dialog_and_clears_other_configs() -> None:
    task = task_row_to_dict(_task_row())
    task["dialog"] = DIALOG

    serialized = _serialize_task(task)

    assert serialized["kind"] == "dialog"
    assert serialized["dialog"] == DIALOG
    assert serialized["h5p"] is None
    assert serialized["visual"] is None
    assert serialized["scratch"] is None
    assert serialized["calliope"] is None
    assert serialized["filius"] is None


def test_preview_failure_records_only_stable_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: list[object] = []
    repo = SimpleNamespace(
        record_dialog_preview_usage=lambda **kwargs: recorded.extend(kwargs["events"])
    )
    generator = SimpleNamespace(
        pop_usage_events=lambda: [SimpleNamespace(error_code=None)]
    )
    monkeypatch.setattr(_routes, "_get_repo", lambda: repo)

    _routes._record_preview_usage(
        generator,
        unit_id="unit-1",
        task_id="task-1",
        author_sub="teacher-1",
        error_code="dialog_ai_unavailable",
    )

    assert len(recorded) == 1
    assert recorded[0].error_code == "dialog_ai_unavailable"
