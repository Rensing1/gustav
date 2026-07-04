"""Small route-level Learning test doubles.

These helpers are intentionally tiny. They let web-route tests exercise a
specific adapter behavior without depending on a live Learning database.
"""

from __future__ import annotations


class VisibleLearningRepo:
    """Authorize every requested task as visible to the current student."""

    def list_submissions(self, *, student_sub: str, course_id: str, task_id: str, limit: int, offset: int) -> list[dict]:
        return []

    def get_task_kind_for_student(self, *, student_sub: str, course_id: str, task_id: str) -> str:
        return "native"
