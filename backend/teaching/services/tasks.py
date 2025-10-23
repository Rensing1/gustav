"""Teaching tasks service layer (Clean Architecture boundary).

Why:
    Encapsulates task-related use cases (list/create/update/delete/reorder)
    so that web adapters remain framework-free and we can unit-test validation
    logic independently of FastAPI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, List, Optional, Protocol, Sequence


class TasksRepoProtocol(Protocol):
    def section_exists_for_author(self, unit_id: str, section_id: str, author_id: str) -> bool:
        ...

    def list_tasks_for_section_owned(self, unit_id: str, section_id: str, author_id: str) -> List[dict]:
        ...

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
        ...

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
        ...

    def delete_task(self, unit_id: str, section_id: str, task_id: str, author_id: str) -> bool:
        ...

    def reorder_section_tasks(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        task_ids: List[str],
    ) -> List[dict]:
        ...


_UNSET = object()


def _normalize_instruction(value: object) -> str:
    if value is None or not isinstance(value, str):
        raise ValueError("invalid_instruction_md")
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("invalid_instruction_md")
    return trimmed


def _normalize_criteria(value: object) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("invalid_criteria")
    normalized: List[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("invalid_criteria")
        trimmed = item.strip()
        if not trimmed:
            raise ValueError("invalid_criteria")
        normalized.append(trimmed)
    if len(normalized) > 10:
        raise ValueError("invalid_criteria")
    return normalized


def _normalize_hints(value: object) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("invalid_hints_md")
    trimmed = value.strip()
    return trimmed or None


def _parse_due_at(value: object) -> Optional[datetime]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("invalid_due_at")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError("invalid_due_at") from exc
    if parsed.tzinfo is None:
        raise ValueError("invalid_due_at")
    return parsed.astimezone(timezone.utc)


def _normalize_max_attempts(value: object) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("invalid_max_attempts")
    try:
        attempts = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_max_attempts") from exc
    if attempts < 1:
        raise ValueError("invalid_max_attempts")
    return attempts


@dataclass
class TasksService:
    """Use cases for teaching tasks (framework-independent)."""

    repo: TasksRepoProtocol

    def list_tasks(self, unit_id: str, section_id: str, author_id: str) -> List[dict]:
        if not self.repo.section_exists_for_author(unit_id, section_id, author_id):
            raise LookupError("section_not_found")
        return self.repo.list_tasks_for_section_owned(unit_id, section_id, author_id)

    def create_task(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        *,
        instruction_md: object,
        criteria: object = None,
        hints_md: object = None,
        due_at: object = None,
        max_attempts: object = None,
    ) -> dict:
        if not self.repo.section_exists_for_author(unit_id, section_id, author_id):
            raise LookupError("section_not_found")
        instruction = _normalize_instruction(instruction_md)
        crit = _normalize_criteria(criteria)
        hints = _normalize_hints(hints_md)
        due_dt = _parse_due_at(due_at)
        attempts = _normalize_max_attempts(max_attempts)
        return self.repo.create_task(
            unit_id,
            section_id,
            author_id,
            instruction_md=instruction,
            criteria=crit,
            hints_md=hints,
            due_at=due_dt,
            max_attempts=attempts,
        )

    def update_task(
        self,
        unit_id: str,
        section_id: str,
        task_id: str,
        author_id: str,
        *,
        instruction_md: object = _UNSET,
        criteria: object = _UNSET,
        hints_md: object = _UNSET,
        due_at: object = _UNSET,
        max_attempts: object = _UNSET,
    ) -> dict:
        if not self.repo.section_exists_for_author(unit_id, section_id, author_id):
            raise LookupError("section_not_found")
        repo_kwargs: dict[str, Any] = {}
        if instruction_md is not _UNSET:
            repo_kwargs["instruction_md"] = _normalize_instruction(instruction_md)
        if criteria is not _UNSET:
            repo_kwargs["criteria"] = _normalize_criteria(criteria)
        if hints_md is not _UNSET:
            repo_kwargs["hints_md"] = _normalize_hints(hints_md)
        if due_at is not _UNSET:
            repo_kwargs["due_at"] = _parse_due_at(due_at)
        if max_attempts is not _UNSET:
            repo_kwargs["max_attempts"] = _normalize_max_attempts(max_attempts)
        result = self.repo.update_task(
            unit_id,
            section_id,
            task_id,
            author_id,
            instruction_md=repo_kwargs.get("instruction_md", _UNSET),
            criteria=repo_kwargs.get("criteria", _UNSET),
            hints_md=repo_kwargs.get("hints_md", _UNSET),
            due_at=repo_kwargs.get("due_at", _UNSET),
            max_attempts=repo_kwargs.get("max_attempts", _UNSET),
        )
        if result is None:
            raise LookupError("task_not_found")
        return result

    def delete_task(self, unit_id: str, section_id: str, task_id: str, author_id: str) -> None:
        deleted = self.repo.delete_task(unit_id, section_id, task_id, author_id)
        if not deleted:
            raise LookupError("task_not_found")

    def reorder_tasks(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        task_ids: List[str],
    ) -> List[dict]:
        return self.repo.reorder_section_tasks(unit_id, section_id, author_id, task_ids)
