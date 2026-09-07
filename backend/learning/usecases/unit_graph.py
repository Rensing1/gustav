"""Student-scoped modular graph reads without HTTP or route dependencies."""

from typing import Protocol

from backend.learning.usecases.modular_unit_access import (
    InvalidModularUnitType,
    StudentCourseUnitsRepository,
    require_visible_modular_unit,
)


class LearningGraphRepository(StudentCourseUnitsRepository, Protocol):
    """Keep both reads scoped to the same authenticated student and course."""

    def get_modular_unit_graph(self, *, student_sub: str, course_id: str, unit_id: str) -> dict: ...


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
        InvalidModularUnitType. The repository remains the source of truth for
        unlock states and safe counters, with no task contents in its projection.
        """
        repo = self.repository
        require_visible_modular_unit(
            repo, student_sub=student_sub, course_id=course_id, unit_id=unit_id
        )
        if not callable(getattr(repo, "get_modular_unit_graph", None)):
            raise GraphRepositoryIncomplete()

        # The DB graph read checks membership again; a concurrent removal must
        # not expose a graph merely because the earlier course listing succeeded.
        try:
            return repo.get_modular_unit_graph(
                student_sub=student_sub, course_id=course_id, unit_id=unit_id
            )
        except ValueError as exc:
            raise InvalidModularUnitType() from exc
