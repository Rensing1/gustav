from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class LearningRepoProtocol(Protocol):
    def is_h5p_content_released_for_student(
        self,
        *,
        student_sub: str,
        course_id: str,
        content_id: str,
    ) -> bool:
        ...


@dataclass
class CheckH5PContentAccessInput:
    student_sub: str
    course_id: str
    content_id: str


class CheckH5PContentAccessUseCase:
    def __init__(self, repo: LearningRepoProtocol) -> None:
        self._repo = repo

    def execute(self, req: CheckH5PContentAccessInput) -> bool:
        """Return True when the student may access this H5P content in the course.

        Intent:
            Provide a tiny, framework-agnostic access check for the H5P sidecar.
            The result is intentionally a boolean only (data minimization).

        Parameters:
            req: Input DTO containing student `sub`, `course_id` and `content_id`.

        Permissions:
            Caller must be an authenticated student. Membership, release visibility
            and H5P task linkage are enforced at the repository/DB boundary.
        """
        return self._repo.is_h5p_content_released_for_student(
            student_sub=req.student_sub,
            course_id=req.course_id,
            content_id=req.content_id,
        )

