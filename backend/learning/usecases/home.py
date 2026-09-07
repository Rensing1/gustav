"""Learner home projection using the same membership-scoped course use case."""

from __future__ import annotations

from backend.learning.usecases.courses import (
    CoursesRepoProtocol,
    ListCoursesInput,
    ListCoursesUseCase,
)


class LearnerHomeUseCase:
    def __init__(self, repo: CoursesRepoProtocol) -> None:
        self._courses = ListCoursesUseCase(repo)

    def execute(self, *, student_sub: str, limit: int, offset: int) -> dict[str, list[dict]]:
        """Build current/past course links for the authenticated learner.

        The HTTP adapter checks the student role and supplies the subject.
        Course visibility, sorting and pagination remain owned by the existing
        course use case and its RLS-backed repository, including former courses.
        """
        result = {}
        for scope in ("current", "past"):
            items = self._courses.execute(
                ListCoursesInput(
                    student_sub=student_sub,
                    limit=limit,
                    offset=offset,
                    scope=scope,
                )
            )
            result[f"{scope}_courses"] = [
                {
                    "id": str(item.get("id") or ""),
                    "title": str(item.get("title") or ""),
                    "href": f"/learning/courses/{item.get('id')}"
                    + ("/archive" if scope == "past" else ""),
                    "school_year_start": item.get("school_year_start"),
                }
                for item in items
                if isinstance(item, dict)
            ]
        return result
