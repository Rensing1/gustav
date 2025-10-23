"""Unit tests for the teaching.TasksService domain logic.

Focus:
    - Input normalisation/validation (instruction, criteria, hints, due_at, max_attempts)
    - Correct delegation to the repository protocol with trimmed/parsed values
    - Error propagation for missing sections or unknown tasks

These tests keep the scope narrow (no FastAPI, no DB) and use a fake repo
implementing the protocol, supporting KISS + Clean Architecture goals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

import pytest

from teaching.services.tasks import TasksService, TasksRepoProtocol, _UNSET


class FakeTasksRepo(TasksRepoProtocol):
    def __init__(self) -> None:
        self.sections: set[tuple[str, str, str]] = set()
        self.created_payload: Dict[str, Any] | None = None
        self.updated_payload: Dict[str, Any] | None = None
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.deleted: list[str] = []
        self.reorders: list[List[str]] = []

    def section_exists_for_author(self, unit_id: str, section_id: str, author_id: str) -> bool:
        return (unit_id, section_id, author_id) in self.sections

    def list_tasks_for_section_owned(self, unit_id: str, section_id: str, author_id: str) -> List[dict]:
        return list(self.tasks.values())

    def create_task(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        *,
        instruction_md: str,
        criteria: List[str],
        hints_md: Optional[str],
        due_at: Optional[datetime],
        max_attempts: Optional[int],
    ) -> dict:
        self.created_payload = {
            "unit_id": unit_id,
            "section_id": section_id,
            "author_id": author_id,
            "instruction_md": instruction_md,
            "criteria": criteria,
            "hints_md": hints_md,
            "due_at": due_at,
            "max_attempts": max_attempts,
        }
        task = {
            "id": "task-1",
            "unit_id": unit_id,
            "section_id": section_id,
            "instruction_md": instruction_md,
            "criteria": criteria,
            "hints_md": hints_md,
            "due_at": due_at.isoformat() if due_at else None,
            "max_attempts": max_attempts,
            "position": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "kind": "native",
        }
        self.tasks[task["id"]] = task
        return task

    def update_task(
        self,
        unit_id: str,
        section_id: str,
        task_id: str,
        author_id: str,
        *,
        instruction_md: Any,
        criteria: Any,
        hints_md: Any,
        due_at: Any,
        max_attempts: Any,
    ) -> Optional[dict]:
        if task_id not in self.tasks:
            return None
        self.updated_payload = {
            "instruction_md": instruction_md,
            "criteria": criteria,
            "hints_md": hints_md,
            "due_at": due_at,
            "max_attempts": max_attempts,
        }
        task = dict(self.tasks[task_id])
        if instruction_md is not _UNSET:
            task["instruction_md"] = instruction_md
        if criteria is not _UNSET:
            task["criteria"] = criteria
        if hints_md is not _UNSET:
            task["hints_md"] = hints_md
        if due_at is not _UNSET:
            task["due_at"] = due_at.isoformat() if due_at else None
        if max_attempts is not _UNSET:
            task["max_attempts"] = max_attempts
        self.tasks[task_id] = task
        return task

    def delete_task(self, unit_id: str, section_id: str, task_id: str, author_id: str) -> bool:
        if task_id in self.tasks:
            self.deleted.append(task_id)
            self.tasks.pop(task_id, None)
            return True
        return False

    def reorder_section_tasks(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        task_ids: List[str],
    ) -> List[dict]:
        self.reorders.append(task_ids)
        return [self.tasks[tid] for tid in task_ids if tid in self.tasks]


@pytest.fixture
def repo() -> FakeTasksRepo:
    fake = FakeTasksRepo()
    fake.sections.add(("unit-1", "section-1", "teacher-1"))
    fake.tasks = {
        "task-1": {
            "id": "task-1",
            "unit_id": "unit-1",
            "section_id": "section-1",
            "instruction_md": "**Solve**",
            "criteria": ["Explain"],
            "hints_md": None,
            "due_at": None,
            "max_attempts": None,
            "position": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "kind": "native",
        }
    }
    return fake


@pytest.fixture
def service(repo: FakeTasksRepo) -> TasksService:
    return TasksService(repo)


def test_create_task_normalizes_inputs(service: TasksService, repo: FakeTasksRepo):
    due = datetime(2025, 1, 2, 8, 0, tzinfo=timezone.utc)
    task = service.create_task(
        "unit-1",
        "section-1",
        "teacher-1",
        instruction_md="  Analyse den Versuch  ",
        criteria=["  Hypothese  ", "Interpretation"],
        hints_md="  Nutze Diagramm  ",
        due_at=due.isoformat(),
        max_attempts="3",
    )
    assert repo.created_payload is not None
    assert repo.created_payload["instruction_md"] == "Analyse den Versuch"
    assert repo.created_payload["criteria"] == ["Hypothese", "Interpretation"]
    assert repo.created_payload["hints_md"] == "Nutze Diagramm"
    assert isinstance(repo.created_payload["due_at"], datetime)
    assert repo.created_payload["due_at"].tzinfo == timezone.utc
    assert repo.created_payload["max_attempts"] == 3
    assert task["kind"] == "native"


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({"instruction_md": None}, "invalid_instruction_md"),
        ({"instruction_md": "   "}, "invalid_instruction_md"),
        ({"criteria": "string"}, "invalid_criteria"),
        ({"criteria": ["", "ok"]}, "invalid_criteria"),
        ({"criteria": [f"K{i}" for i in range(12)]}, "invalid_criteria"),
        ({"due_at": "2025-01-01T10:00:00"}, "invalid_due_at"),  # missing tz
        ({"due_at": "bad"}, "invalid_due_at"),
        ({"max_attempts": 0}, "invalid_max_attempts"),
        ({"max_attempts": True}, "invalid_max_attempts"),
    ],
)
def test_create_task_validation_errors(service: TasksService, repo: FakeTasksRepo, kwargs, expected):
    params = {"instruction_md": "Analyse"}
    params.update(kwargs)
    with pytest.raises(ValueError) as exc:
        service.create_task("unit-1", "section-1", "teacher-1", **params)
    assert str(exc.value) == expected
    assert repo.created_payload is None


def test_create_task_unknown_section(service: TasksService):
    with pytest.raises(LookupError):
        service.create_task("unit-x", "section-x", "teacher-1", instruction_md="Aufgabe")


def test_update_task_delegates_only_provided_fields(service: TasksService, repo: FakeTasksRepo):
    updated = service.update_task(
        "unit-1",
        "section-1",
        "task-1",
        "teacher-1",
        criteria=["Analysiere"],
        max_attempts=5,
    )
    assert repo.updated_payload == {
        "instruction_md": _UNSET,
        "criteria": ["Analysiere"],
        "hints_md": _UNSET,
        "due_at": _UNSET,
        "max_attempts": 5,
    }
    assert updated["criteria"] == ["Analysiere"]
    assert updated["max_attempts"] == 5


def test_update_task_invalid_inputs_raise(service: TasksService, repo: FakeTasksRepo):
    with pytest.raises(ValueError) as exc:
        service.update_task(
            "unit-1",
            "section-1",
            "task-1",
            "teacher-1",
            instruction_md="   ",
        )
    assert str(exc.value) == "invalid_instruction_md"


def test_update_task_unknown_section(service: TasksService, repo: FakeTasksRepo):
    repo.section_exists_for_author = lambda *args: False  # type: ignore
    with pytest.raises(LookupError):
        service.update_task(
            "unit-1",
            "section-1",
            "task-1",
            "teacher-1",
            criteria=["X"],
        )


def test_update_task_unknown_task_returns_lookup_error(service: TasksService, repo: FakeTasksRepo):
    with pytest.raises(LookupError):
        service.update_task(
            "unit-1",
            "section-1",
            "missing",
            "teacher-1",
            criteria=["X"],
        )


def test_delete_and_reorder_delegate(service: TasksService, repo: FakeTasksRepo):
    service.delete_task("unit-1", "section-1", "task-1", "teacher-1")
    assert repo.deleted == ["task-1"]

    template = {
        "unit_id": "unit-1",
        "section_id": "section-1",
        "instruction_md": "Instruktion",
        "criteria": ["Hinweis"],
        "hints_md": None,
        "due_at": None,
        "max_attempts": None,
        "position": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "kind": "native",
    }
    repo.tasks = {
        "task-2": {**template, "id": "task-2"},
        "task-3": {**template, "id": "task-3"},
    }
    service.reorder_tasks("unit-1", "section-1", "teacher-1", ["task-3", "task-2"])
    assert repo.reorders == [["task-3", "task-2"]]
