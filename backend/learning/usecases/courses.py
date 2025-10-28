from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class CoursesRepoProtocol(Protocol):
    def list_courses_for_student(self, *, student_sub: str, limit: int, offset: int) -> list[dict]:
        ...

    def list_units_for_student_course(self, *, student_sub: str, course_id: str) -> list[dict]:
        ...


@dataclass
class ListCoursesInput:
    student_sub: str
    limit: int
    offset: int


class ListCoursesUseCase:
    def __init__(self, repo: CoursesRepoProtocol) -> None:
        self._repo = repo

    def execute(self, req: ListCoursesInput) -> list[dict]:
        """Return student's courses alphabetically with safe pagination bounds.

        Why:
            Keep pagination and access semantics in the use case layer and keep
            the web adapter thin. The repository enforces RLS and membership.

        Permissions:
            Caller must be a student; underlying repo filters to membership.
        """
        limit = max(1, min(100, int(req.limit)))
        offset = max(0, int(req.offset))
        return self._repo.list_courses_for_student(student_sub=req.student_sub, limit=limit, offset=offset)


@dataclass
class ListCourseUnitsInput:
    student_sub: str
    course_id: str


class ListCourseUnitsUseCase:
    def __init__(self, repo: CoursesRepoProtocol) -> None:
        self._repo = repo

    def execute(self, req: ListCourseUnitsInput) -> list[dict]:
        """Return units of a course for the student ordered by module position.

        Behavior:
            - Valid course membership is enforced by the repository/DB helper.
            - Returns a list of { unit: UnitPublic, position: int }.

        Permissions:
            Caller must be the enrolled student of the course.
        """
        return self._repo.list_units_for_student_course(student_sub=req.student_sub, course_id=req.course_id)
