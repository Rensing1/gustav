"""Student-scoped modular graph reads without HTTP or route dependencies."""

from typing import Protocol
from uuid import UUID


class LearningGraphRepository(Protocol):
    """Keep both reads scoped to the same authenticated student and course."""

    def list_units_for_student_course(self, *, student_sub: str, course_id: str) -> list[dict]: ...
    def get_modular_unit_graph(self, *, student_sub: str, course_id: str, unit_id: str) -> dict: ...


class GraphInvalidUnitType(ValueError):
    """The visible unit is not modular."""


class GraphRepositoryIncomplete(RuntimeError):
    """The adapter cannot read a modular graph."""


class LearningGraphUseCase:
    def __init__(self, repository: LearningGraphRepository):
        self.repository = repository

    def read(self, student_sub: str, course_id: str, unit_id: str) -> dict:
        """Read a member's assigned modular unit with its own unlock states.

        Supply an authenticated student subject and canonical UUID strings.
        Membership and assignment are checked before accessing graph metadata.
        Missing/hidden resources raise LookupError; a visible linear unit raises
        GraphInvalidUnitType. The repository remains the source of truth for
        unlock states and safe counters, with no task contents in its projection.
        """
        repo = self.repository
        rows = repo.list_units_for_student_course(student_sub=student_sub, course_id=course_id)
        unit = None
        for item in rows:
            candidate = item.get("unit")
            if not isinstance(candidate, dict):
                continue
            try:
                candidate_id = str(UUID(str(candidate.get("id"))))
            except (ValueError, TypeError):
                continue
            if candidate_id == unit_id:
                unit = candidate
                break
        if not unit:
            raise LookupError("unit_not_visible")
        if str(unit.get("unit_type") or "").strip().lower() != "modular":
            raise GraphInvalidUnitType()
        if not callable(getattr(repo, "get_modular_unit_graph", None)):
            raise GraphRepositoryIncomplete()

        # The DB graph read checks membership again; a concurrent removal must
        # not expose a graph merely because the earlier course listing succeeded.
        try:
            return repo.get_modular_unit_graph(
                student_sub=student_sub, course_id=course_id, unit_id=unit_id
            )
        except ValueError as exc:
            raise GraphInvalidUnitType() from exc
