"""Red/green use-case tests for practice task authoring."""

from __future__ import annotations

from typing import Any

import pytest

from backend.teaching.services.tasks import TasksService


class Repo:
    def __init__(self, *, module_kind: str = "practice", existing: dict[str, Any] | None = None) -> None:
        self.module_kind = module_kind
        self.created: dict[str, Any] | None = None
        self.updated: dict[str, Any] | None = None
        self.existing = existing or {
            "id": "task-1",
            "instruction_md": "Erkläre den Begriff.",
            "criteria": ["Fachlich richtig"],
            "teacher_context_md": "Bezug zum Unterricht",
            "model_solution_md": "Eine fachlich richtige Erklärung.",
            "due_at": None,
            "max_attempts": None,
            "kind": "native",
        }

    def section_exists_for_author(self, unit_id: str, section_id: str, author_id: str) -> bool:
        return True

    def get_section_module_kind_for_author(self, unit_id: str, section_id: str, author_id: str) -> str:
        return self.module_kind

    def list_tasks_for_section_owned(self, unit_id: str, section_id: str, author_id: str) -> list[dict]:
        return [dict(self.existing)]

    def create_task(self, unit_id: str, section_id: str, author_id: str, **kwargs: Any) -> dict:
        self.created = kwargs
        return {"id": "task-1", **kwargs}

    def update_task(self, unit_id: str, section_id: str, task_id: str, author_id: str, **kwargs: Any) -> dict:
        self.updated = kwargs
        return {**self.existing, **kwargs}


def test_complete_native_practice_task_is_delegated() -> None:
    repo = Repo()
    task = TasksService(repo).create_task(  # type: ignore[arg-type]
        "unit-1",
        "section-1",
        "teacher-1",
        instruction_md=" Erkläre den Begriff. ",
        criteria=[" Fachlich richtig "],
        teacher_context_md=" Bezug zum Unterricht ",
        model_solution_md=" Musterantwort ",
    )

    assert task["model_solution_md"] == "Musterantwort"
    assert repo.created is not None
    assert repo.created["due_at"] is None
    assert repo.created["max_attempts"] is None


@pytest.mark.parametrize(
    ("patch", "detail"),
    [
        ({"criteria": []}, "practice_fields_required"),
        ({"teacher_context_md": None}, "practice_fields_required"),
        ({"model_solution_md": None}, "practice_fields_required"),
        ({"due_at": "2026-08-09T08:00:00Z"}, "practice_schedule_fields_forbidden"),
        ({"max_attempts": 2}, "practice_schedule_fields_forbidden"),
        ({"visual": {}}, "practice_task_kind_not_supported"),
    ],
)
def test_invalid_native_practice_task_is_rejected(patch: dict[str, object], detail: str) -> None:
    payload: dict[str, object] = {
        "instruction_md": "Erkläre den Begriff.",
        "criteria": ["Fachlich richtig"],
        "teacher_context_md": "Kontext",
        "model_solution_md": "Musterantwort",
    }
    payload.update(patch)

    with pytest.raises(ValueError, match=detail):
        TasksService(Repo()).create_task("unit-1", "section-1", "teacher-1", **payload)  # type: ignore[arg-type]


def test_h5p_practice_task_needs_no_model_solution() -> None:
    repo = Repo()
    TasksService(repo).create_task(  # type: ignore[arg-type]
        "unit-1",
        "section-1",
        "teacher-1",
        instruction_md="Bearbeite die interaktive Aufgabe.",
        h5p={"content_id": "42", "display_options": {}},
    )
    assert repo.created is not None
    assert repo.created["kind"] == "h5p"


def test_practice_update_validates_the_merged_task() -> None:
    service = TasksService(Repo())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="practice_fields_required"):
        service.update_task(
            "unit-1",
            "section-1",
            "task-1",
            "teacher-1",
            model_solution_md=None,
        )


def test_learning_task_keeps_all_fields_optional() -> None:
    repo = Repo(module_kind="learning")
    TasksService(repo).create_task(  # type: ignore[arg-type]
        "unit-1",
        "section-1",
        "teacher-1",
        instruction_md="Normale Aufgabe",
        due_at="2026-08-09T08:00:00Z",
        max_attempts=2,
    )
    assert repo.created is not None
    assert repo.created["model_solution_md"] is None
