"""Teaching service layer for the student live overview.

Why:
    The web adapter needs a teacher-facing snapshot that combines teaching
    structure (course units/tasks) with learning aggregates (latest submission
    status for one student). This module keeps that orchestration independent
    of FastAPI/SSR details so the behavior can be tested without HTTP.
"""

from __future__ import annotations

import sys
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence
from uuid import UUID

# Temporary compatibility while legacy tests still import `teaching.services.live_student_overview`.
if __name__ == "backend.teaching.services.live_student_overview":
    sys.modules.setdefault("teaching.services.live_student_overview", sys.modules[__name__])
elif __name__ == "teaching.services.live_student_overview":
    sys.modules.setdefault("backend.teaching.services.live_student_overview", sys.modules[__name__])
for _parent_name, _attribute_name in (
    ("teaching.services", "live_student_overview"),
    ("backend.teaching.services", "live_student_overview"),
):
    _parent = sys.modules.get(_parent_name)
    if _parent is not None:
        setattr(_parent, _attribute_name, sys.modules[__name__])


MAX_UNIT_IDS = 50


class StudentLiveOverviewRepoProtocol(Protocol):
    def list_course_units_for_owner(self, course_id: str, owner_sub: str) -> List[dict]:
        ...

    def course_has_member(self, course_id: str, owner_sub: str, student_sub: str) -> bool:
        ...

    def list_tasks_for_course_units_owner(
        self,
        course_id: str,
        unit_ids: Sequence[str],
        owner_sub: str,
    ) -> List[dict]:
        ...

    def list_tasks_for_course_unit_owner(self, course_id: str, unit_id: str, owner_sub: str) -> List[dict]:
        ...

    def list_latest_submission_aggregates_for_owner(
        self,
        *,
        course_id: str,
        owner_sub: str,
        student_sub: str,
        unit_ids: Sequence[str],
    ) -> List[dict]:
        ...


def _normalize_unit_ids(raw_unit_ids: Sequence[str] | None) -> tuple[List[str], bool]:
    """Normalize filter values while preserving whether the query key was present.

    Returns:
        (normalized_unit_ids, explicitly_present)
    """
    if raw_unit_ids is None:
        return [], False
    normalized: List[str] = []
    seen: set[str] = set()
    for raw in raw_unit_ids:
        value = _canonicalize_uuid_like(str(raw or "").strip())
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized, True


def _canonicalize_uuid_like(value: str) -> str:
    """Return a canonical UUID string when possible.

    Why:
        Query params arrive as strings and may differ only by casing. The
        teacher overview treats these values as semantic UUIDs, so valid UUIDs
        must be deduplicated case-insensitively before membership checks.
    """
    if not value:
        return ""
    try:
        return str(UUID(value))
    except (ValueError, TypeError):
        return value


@dataclass(frozen=True)
class StudentLiveOverviewTask:
    id: str
    instruction_md: str
    position: int
    kind: str
    has_submission: bool
    average_score: float | None
    h5p_completed: bool | None


@dataclass(frozen=True)
class StudentLiveOverviewUnit:
    id: str
    title: str
    tasks: List[StudentLiveOverviewTask]


@dataclass(frozen=True)
class StudentLiveOverview:
    student_sub: str
    units: List[StudentLiveOverviewUnit]

    def to_dict(self, *, student_name: str) -> Dict[str, Any]:
        return {
            "student": {"sub": self.student_sub, "name": student_name},
            "units": [asdict(unit) for unit in self.units],
        }


@dataclass
class StudentLiveOverviewService:
    """Build a teacher-facing live overview for one student across course units."""

    repo: StudentLiveOverviewRepoProtocol

    def build(
        self,
        *,
        course_id: str,
        owner_sub: str,
        student_sub: str,
        raw_unit_ids: Sequence[str] | None,
    ) -> StudentLiveOverview:
        unit_ids, unit_ids_present = _normalize_unit_ids(raw_unit_ids)
        if len(unit_ids) > MAX_UNIT_IDS:
            raise ValueError("too_many_unit_ids")

        available_units = self.repo.list_course_units_for_owner(course_id, owner_sub)
        available_ids = [str(item.get("id") or "") for item in available_units if isinstance(item, dict)]
        available_set = set(available_ids)

        if unit_ids_present:
            selected_ids = list(unit_ids)
            if any(unit_id not in available_set for unit_id in selected_ids):
                raise LookupError("unit_not_in_course")
        else:
            selected_ids = available_ids

        if not self.repo.course_has_member(course_id, owner_sub, student_sub):
            raise LookupError("student_not_in_course")

        if unit_ids_present and not selected_ids:
            return StudentLiveOverview(student_sub=student_sub, units=[])

        tasks_by_unit = self._list_tasks_by_unit(
            course_id=course_id,
            owner_sub=owner_sub,
            selected_ids=selected_ids,
        )
        aggregates = self.repo.list_latest_submission_aggregates_for_owner(
            course_id=course_id,
            owner_sub=owner_sub,
            student_sub=student_sub,
            unit_ids=selected_ids,
        )
        by_task: Dict[tuple[str, str], dict] = {}
        for item in aggregates:
            if not isinstance(item, dict):
                continue
            key = (str(item.get("unit_id") or ""), str(item.get("task_id") or ""))
            by_task[key] = item

        units_out: List[StudentLiveOverviewUnit] = []
        for unit in available_units:
            unit_id = str(unit.get("id") or "")
            if unit_id not in selected_ids:
                continue
            tasks_out: List[StudentLiveOverviewTask] = []
            for task in tasks_by_unit.get(unit_id, []):
                task_id = str(task.get("id") or "")
                aggregate = by_task.get((unit_id, task_id), {})
                tasks_out.append(
                    StudentLiveOverviewTask(
                        id=task_id,
                        instruction_md=str(task.get("instruction_md") or ""),
                        position=int(task.get("position") or 0),
                        kind=str(task.get("kind") or "native"),
                        has_submission=bool(aggregate.get("has_submission")),
                        average_score=_to_float_or_none(aggregate.get("average_score")),
                        h5p_completed=_to_bool_or_none(aggregate.get("h5p_completed")),
                    )
                )
            units_out.append(
                StudentLiveOverviewUnit(
                    id=unit_id,
                    title=str(unit.get("title") or ""),
                    tasks=tasks_out,
                )
            )
        return StudentLiveOverview(student_sub=student_sub, units=units_out)

    def _list_tasks_by_unit(
        self,
        *,
        course_id: str,
        owner_sub: str,
        selected_ids: Sequence[str],
    ) -> Dict[str, List[dict]]:
        """Load selected tasks in one repo call when the adapter supports it."""
        tasks_by_unit: Dict[str, List[dict]] = {str(unit_id): [] for unit_id in selected_ids}
        batch_loader = getattr(self.repo, "list_tasks_for_course_units_owner", None)
        if callable(batch_loader):
            tasks_raw = batch_loader(course_id, selected_ids, owner_sub) or []
            for item in tasks_raw:
                if not isinstance(item, dict):
                    continue
                unit_id = str(item.get("unit_id") or "")
                if unit_id not in tasks_by_unit:
                    continue
                tasks_by_unit[unit_id].append(item)
        else:
            for unit_id in selected_ids:
                tasks_raw = self.repo.list_tasks_for_course_unit_owner(course_id, unit_id, owner_sub)
                tasks_by_unit[str(unit_id)] = [task for task in tasks_raw if isinstance(task, dict)]

        for unit_id, items in tasks_by_unit.items():
            items.sort(key=lambda item: (int(item.get("position") or 0), str(item.get("id") or "")))
            tasks_by_unit[unit_id] = items
        return tasks_by_unit


def _to_float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_bool_or_none(value: object) -> bool | None:
    if value is None:
        return None
    return bool(value)


__all__ = [
    "MAX_UNIT_IDS",
    "StudentLiveOverview",
    "StudentLiveOverviewService",
    "StudentLiveOverviewTask",
    "StudentLiveOverviewUnit",
]
