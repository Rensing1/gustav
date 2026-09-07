"""Student module reads with existing DB-owned visibility and unlock rules."""

from typing import Protocol

from backend.learning.usecases.modular_unit_access import (
    InvalidModularUnitType,
    StudentCourseUnitsRepository,
    require_visible_modular_unit,
)


class LearningModuleRepository(StudentCourseUnitsRepository, Protocol):
    def get_modular_module_content(
        self,
        *,
        student_sub: str,
        course_id: str,
        unit_id: str,
        module_id: str,
        include_materials: bool,
        include_tasks: bool,
    ) -> dict: ...


class ModuleRepositoryIncomplete(RuntimeError):
    """The adapter cannot supply module contents."""


class LearningModuleUseCase:
    def __init__(self, repository: LearningModuleRepository):
        self.repository = repository

    def read(
        self,
        student_sub: str,
        course_id: str,
        unit_id: str,
        module_id: str,
        *,
        include_materials: bool,
        include_tasks: bool,
    ) -> dict:
        """Read only a member's open/done module with selected embedded resources.

        Supply authenticated student identity and canonical UUIDs. Membership
        and assignment precede content access. The repository rechecks access,
        derives unlock state in SQL, and excludes private teacher fields.
        Locked, foreign and missing modules remain indistinguishable LookupErrors.
        """
        repo = self.repository
        require_visible_modular_unit(
            repo, student_sub=student_sub, course_id=course_id, unit_id=unit_id
        )
        if not callable(getattr(repo, "get_modular_module_content", None)):
            raise ModuleRepositoryIncomplete()
        try:
            return repo.get_modular_module_content(
                student_sub=student_sub,
                course_id=course_id,
                unit_id=unit_id,
                module_id=module_id,
                include_materials=include_materials,
                include_tasks=include_tasks,
            )
        except ValueError as exc:
            raise InvalidModularUnitType() from exc
