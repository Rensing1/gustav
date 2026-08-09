"""Teaching tasks service layer (Clean Architecture boundary).

Why:
    Encapsulates task-related use cases (list/create/update/delete/reorder)
    so that web adapters remain framework-free and we can unit-test validation
    logic independently of FastAPI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple


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
        teacher_context_md: Optional[str],
        due_at: Optional[datetime],
        max_attempts: Optional[int],
        kind: str,
        h5p_content_id: Optional[str],
        h5p_display_options: Dict[str, Any],
        dialog_config: Optional[Dict[str, Any]] = None,
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
        teacher_context_md: Any,
        due_at: Any,
        max_attempts: Any,
        kind: Any,
        h5p_content_id: Any,
        h5p_display_options: Any,
        dialog_config: Any,
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


def _normalize_teacher_context(value: object) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("invalid_teacher_context_md")
    trimmed = value.strip()
    return trimmed or None


def _parse_due_at(value: object) -> Optional[datetime]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("invalid_due_at")
    # Accept both '+00:00' and 'Z' suffix for UTC; trim whitespace
    s = value.strip()
    if s.endswith("Z") or s.endswith("z"):
        s = s[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(s)
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


def _normalize_h5p_config(value: object) -> Tuple[Optional[str], Dict[str, Any]]:
    if not isinstance(value, dict):
        raise ValueError("invalid_h5p_config")
    allowed = {"content_id", "display_options"}
    if any(k not in allowed for k in value.keys()):
        raise ValueError("invalid_h5p_config")
    raw_content_id = value.get("content_id")
    content_id: Optional[str]
    if raw_content_id is None:
        content_id = None
    elif isinstance(raw_content_id, str):
        trimmed = raw_content_id.strip()
        if trimmed and not re.fullmatch(r"[0-9]+", trimmed):
            raise ValueError("invalid_h5p_config")
        content_id = trimmed or None
    else:
        raise ValueError("invalid_h5p_config")

    raw_display = value.get("display_options", {})
    if raw_display is None:
        raw_display = {}
    if not isinstance(raw_display, dict):
        raise ValueError("invalid_h5p_config")
    return content_id, dict(raw_display)


def _normalize_visual_config(value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError("invalid_visual_config")
    if value:
        raise ValueError("invalid_visual_config")

def _normalize_scratch_config(value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError("invalid_scratch_config")
    if value:
        raise ValueError("invalid_scratch_config")

def _normalize_calliope_config(value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError("invalid_calliope_config")
    if value:
        raise ValueError("invalid_calliope_config")

def _normalize_filius_config(value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError("invalid_filius_config")
    if value:
        raise ValueError("invalid_filius_config")


def normalize_dialog_config(value: object) -> Dict[str, Any]:
    """Validate and normalize the teacher-authored dialog configuration.

    Why:
        The dialog prompt contains both learner-visible and internal fields.
        Normalizing it at the use-case boundary keeps HTTP and persistence
        adapters simple and prevents unknown prompt fields from being stored.
    """

    if not isinstance(value, dict):
        raise ValueError("invalid_dialog_config")
    required_limits = {
        "partner_name": 120,
        "partner_description_md": 2000,
        "role_md": 4000,
        "learning_goal_md": 2000,
        "opening_message_md": 2000,
    }
    allowed = {*required_limits, "response_mode", "max_rounds", "closing_prompt_md"}
    if set(value) - allowed:
        raise ValueError("invalid_dialog_config")

    normalized: Dict[str, Any] = {}
    for field, max_length in required_limits.items():
        raw = value.get(field)
        if not isinstance(raw, str):
            raise ValueError("invalid_dialog_config")
        cleaned = raw.strip()
        if not cleaned or len(cleaned) > max_length:
            raise ValueError("invalid_dialog_config")
        normalized[field] = cleaned

    response_mode = value.get("response_mode")
    if response_mode not in {"free_text", "hybrid"}:
        raise ValueError("invalid_dialog_config")
    normalized["response_mode"] = response_mode

    max_rounds = value.get("max_rounds", 8)
    if isinstance(max_rounds, bool):
        raise ValueError("invalid_dialog_config")
    try:
        max_rounds = int(max_rounds)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_dialog_config") from exc
    if not 1 <= max_rounds <= 12:
        raise ValueError("invalid_dialog_config")
    normalized["max_rounds"] = max_rounds

    closing = value.get("closing_prompt_md")
    if closing is None:
        normalized["closing_prompt_md"] = None
    elif isinstance(closing, str):
        closing = closing.strip()
        if not closing or len(closing) > 2000:
            raise ValueError("invalid_dialog_config")
        normalized["closing_prompt_md"] = closing
    else:
        raise ValueError("invalid_dialog_config")
    return normalized


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
        teacher_context_md: object = None,
        due_at: object = None,
        max_attempts: object = None,
        h5p: object | None = None,
        visual: object | None = None,
        scratch: object | None = None,
        calliope: object | None = None,
        filius: object | None = None,
        dialog: object | None = None,
    ) -> dict:
        if not self.repo.section_exists_for_author(unit_id, section_id, author_id):
            raise LookupError("section_not_found")
        instruction = _normalize_instruction(instruction_md)
        crit = _normalize_criteria(criteria)
        teacher_context = _normalize_teacher_context(teacher_context_md)
        due_dt = _parse_due_at(due_at)
        attempts = _normalize_max_attempts(max_attempts)
        kind_configs = [h5p is not None, visual is not None, scratch is not None, calliope is not None, filius is not None, dialog is not None]
        if sum(1 for flag in kind_configs if flag) > 1:
            raise ValueError("invalid_task_kind_config")
        if h5p is not None:
            h5p_content_id, h5p_display_options = _normalize_h5p_config(h5p)
            kind = "h5p"
        elif visual is not None:
            _normalize_visual_config(visual)
            h5p_content_id, h5p_display_options = None, {}
            kind = "visual"
        elif scratch is not None:
            _normalize_scratch_config(scratch)
            h5p_content_id, h5p_display_options = None, {}
            kind = "scratch"
        elif calliope is not None:
            _normalize_calliope_config(calliope)
            h5p_content_id, h5p_display_options = None, {}
            kind = "calliope"
        elif filius is not None:
            _normalize_filius_config(filius)
            h5p_content_id, h5p_display_options = None, {}
            kind = "filius"
        elif dialog is not None:
            dialog_config = normalize_dialog_config(dialog)
            h5p_content_id, h5p_display_options = None, {}
            kind = "dialog"
        else:
            h5p_content_id, h5p_display_options = None, {}
            kind = "native"
        repo_kwargs: dict[str, Any] = {}
        if dialog is not None:
            repo_kwargs["dialog_config"] = dialog_config
        return self.repo.create_task(
            unit_id,
            section_id,
            author_id,
            instruction_md=instruction,
            criteria=crit,
            teacher_context_md=teacher_context,
            due_at=due_dt,
            max_attempts=attempts,
            kind=kind,
            h5p_content_id=h5p_content_id,
            h5p_display_options=h5p_display_options,
            **repo_kwargs,
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
        teacher_context_md: object = _UNSET,
        due_at: object = _UNSET,
        max_attempts: object = _UNSET,
        h5p: object = _UNSET,
        visual: object = _UNSET,
        scratch: object = _UNSET,
        calliope: object = _UNSET,
        filius: object = _UNSET,
        dialog: object = _UNSET,
    ) -> dict:
        if not self.repo.section_exists_for_author(unit_id, section_id, author_id):
            raise LookupError("section_not_found")
        repo_kwargs: dict[str, Any] = {}
        if instruction_md is not _UNSET:
            repo_kwargs["instruction_md"] = _normalize_instruction(instruction_md)
        if criteria is not _UNSET:
            repo_kwargs["criteria"] = _normalize_criteria(criteria)
        if teacher_context_md is not _UNSET:
            repo_kwargs["teacher_context_md"] = _normalize_teacher_context(teacher_context_md)
        if due_at is not _UNSET:
            repo_kwargs["due_at"] = _parse_due_at(due_at)
        if max_attempts is not _UNSET:
            repo_kwargs["max_attempts"] = _normalize_max_attempts(max_attempts)
        kind_updates = [h5p is not _UNSET, visual is not _UNSET, scratch is not _UNSET, calliope is not _UNSET, filius is not _UNSET, dialog is not _UNSET]
        if sum(1 for flag in kind_updates if flag) > 1:
            raise ValueError("invalid_task_kind_config")
        if h5p is not _UNSET:
            if h5p is None:
                repo_kwargs["kind"] = "native"
                repo_kwargs["h5p_content_id"] = None
                repo_kwargs["h5p_display_options"] = {}
            else:
                h5p_content_id, h5p_display_options = _normalize_h5p_config(h5p)
                repo_kwargs["kind"] = "h5p"
                repo_kwargs["h5p_content_id"] = h5p_content_id
                repo_kwargs["h5p_display_options"] = h5p_display_options
        if visual is not _UNSET:
            if visual is None:
                repo_kwargs["kind"] = "native"
                repo_kwargs["h5p_content_id"] = None
                repo_kwargs["h5p_display_options"] = {}
            else:
                _normalize_visual_config(visual)
                repo_kwargs["kind"] = "visual"
                repo_kwargs["h5p_content_id"] = None
                repo_kwargs["h5p_display_options"] = {}
        if scratch is not _UNSET:
            if scratch is None:
                repo_kwargs["kind"] = "native"
                repo_kwargs["h5p_content_id"] = None
                repo_kwargs["h5p_display_options"] = {}
            else:
                _normalize_scratch_config(scratch)
                repo_kwargs["kind"] = "scratch"
                repo_kwargs["h5p_content_id"] = None
                repo_kwargs["h5p_display_options"] = {}
        if calliope is not _UNSET:
            if calliope is None:
                repo_kwargs["kind"] = "native"
                repo_kwargs["h5p_content_id"] = None
                repo_kwargs["h5p_display_options"] = {}
            else:
                _normalize_calliope_config(calliope)
                repo_kwargs["kind"] = "calliope"
                repo_kwargs["h5p_content_id"] = None
                repo_kwargs["h5p_display_options"] = {}
        if filius is not _UNSET:
            if filius is None:
                repo_kwargs["kind"] = "native"
                repo_kwargs["h5p_content_id"] = None
                repo_kwargs["h5p_display_options"] = {}
            else:
                _normalize_filius_config(filius)
                repo_kwargs["kind"] = "filius"
                repo_kwargs["h5p_content_id"] = None
                repo_kwargs["h5p_display_options"] = {}
        if dialog is not _UNSET:
            if dialog is None:
                repo_kwargs["kind"] = "native"
                repo_kwargs["dialog_config"] = None
            else:
                repo_kwargs["kind"] = "dialog"
                repo_kwargs["h5p_content_id"] = None
                repo_kwargs["h5p_display_options"] = {}
                repo_kwargs["dialog_config"] = normalize_dialog_config(dialog)
        result = self.repo.update_task(
            unit_id,
            section_id,
            task_id,
            author_id,
            **repo_kwargs,
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
