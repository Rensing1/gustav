"""Shared student/course assignment rules for graph and module-content reads."""

from typing import Protocol
from uuid import UUID


class StudentCourseUnitsRepository(Protocol):
    def list_units_for_student_course(self, *, student_sub: str, course_id: str) -> list[dict]: ...


class InvalidModularUnitType(ValueError):
    """The visible course unit is not modular."""


def require_visible_modular_unit(
    repository: StudentCourseUnitsRepository, *, student_sub: str, course_id: str, unit_id: str
) -> None:
    """Require membership and a modular unit assigned to the student's course.

    Callers supply authenticated identity and canonical UUID strings. Hidden
    resources raise LookupError without disclosing whether they exist. Actual
    graph/content reads must still recheck access at their DB boundary.
    """
    rows = repository.list_units_for_student_course(student_sub=student_sub, course_id=course_id)
    for item in rows:
        unit = item.get("unit")
        if not isinstance(unit, dict):
            continue
        try:
            candidate_id = str(UUID(str(unit.get("id"))))
        except (ValueError, TypeError):
            continue
        if candidate_id != unit_id:
            continue
        if str(unit.get("unit_type") or "").strip().lower() != "modular":
            raise InvalidModularUnitType()
        return
    raise LookupError("unit_not_visible")
