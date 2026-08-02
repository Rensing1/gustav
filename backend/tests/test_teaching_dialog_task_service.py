"""TDD contract for dialog-task authoring in the Teaching use case."""

from __future__ import annotations

from typing import Any

import pytest

from backend.teaching.services.tasks import TasksService


VALID_DIALOG = {
    "partner_name": "Vertreterin",
    "partner_description_md": "Eine Gesprächspartnerin mit bürgerrechtlicher Perspektive.",
    "role_md": "Vertrete die bürgerrechtliche Perspektive und stelle Rückfragen.",
    "learning_goal_md": "Zielkonflikte zwischen Sicherheit und Freiheit erkennen.",
    "opening_message_md": "Welche Frage möchtest du zuerst diskutieren?",
    "response_mode": "hybrid",
    "max_rounds": 8,
    "closing_prompt_md": "Fasse dein begründetes Urteil zusammen.",
}


class Repo:
    def __init__(self) -> None:
        self.created: dict[str, Any] | None = None
        self.updated: dict[str, Any] | None = None

    def section_exists_for_author(self, unit_id: str, section_id: str, author_id: str) -> bool:
        return True

    def create_task(self, unit_id: str, section_id: str, author_id: str, **kwargs: Any) -> dict:
        self.created = kwargs
        return {"id": "task-1", "kind": kwargs["kind"], "dialog": kwargs.get("dialog_config")}

    def update_task(self, unit_id: str, section_id: str, task_id: str, author_id: str, **kwargs: Any) -> dict:
        self.updated = kwargs
        return {"id": task_id, "kind": kwargs.get("kind", "dialog"), "dialog": kwargs.get("dialog_config")}


def test_create_dialog_task_normalizes_config_and_sets_kind() -> None:
    repo = Repo()
    service = TasksService(repo)  # type: ignore[arg-type]

    task = service.create_task(
        "unit-1",
        "section-1",
        "teacher-1",
        instruction_md=" Diskutiere die Position. ",
        dialog={**VALID_DIALOG, "partner_name": "  Vertreterin  ", "closing_prompt_md": "  Urteil  "},
    )

    assert task["kind"] == "dialog"
    assert repo.created is not None
    assert repo.created["dialog_config"]["partner_name"] == "Vertreterin"
    assert repo.created["dialog_config"]["closing_prompt_md"] == "Urteil"
    assert repo.created["dialog_config"]["max_rounds"] == 8


@pytest.mark.parametrize(
    "patch",
    [
        {"partner_name": ""},
        {"partner_description_md": ""},
        {"role_md": ""},
        {"learning_goal_md": ""},
        {"opening_message_md": ""},
        {"response_mode": "buttons"},
        {"max_rounds": 0},
        {"max_rounds": 13},
        {"closing_prompt_md": ""},
        {"unexpected": "value"},
    ],
)
def test_create_dialog_task_rejects_invalid_config(patch: dict[str, object]) -> None:
    repo = Repo()
    service = TasksService(repo)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="invalid_dialog_config"):
        service.create_task(
            "unit-1",
            "section-1",
            "teacher-1",
            instruction_md="Diskutiere.",
            dialog={**VALID_DIALOG, **patch},
        )


def test_create_dialog_task_is_mutually_exclusive() -> None:
    service = TasksService(Repo())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="invalid_task_kind_config"):
        service.create_task(
            "unit-1",
            "section-1",
            "teacher-1",
            instruction_md="Diskutiere.",
            dialog=VALID_DIALOG,
            visual={},
        )


def test_update_dialog_task_delegates_the_normalized_config() -> None:
    repo = Repo()
    service = TasksService(repo)  # type: ignore[arg-type]

    service.update_task(
        "unit-1",
        "section-1",
        "task-1",
        "teacher-1",
        dialog={**VALID_DIALOG, "max_rounds": 12},
    )

    assert repo.updated is not None
    assert repo.updated["kind"] == "dialog"
    assert repo.updated["dialog_config"]["max_rounds"] == 12
