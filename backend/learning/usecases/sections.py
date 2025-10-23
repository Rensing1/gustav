from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class LearningRepoProtocol(Protocol):
    def list_released_sections(
        self,
        *,
        student_sub: str,
        course_id: str,
        include_materials: bool,
        include_tasks: bool,
        limit: int,
        offset: int,
    ) -> list[dict]:
        ...


@dataclass
class ListSectionsInput:
    student_sub: str
    course_id: str
    include_materials: bool
    include_tasks: bool
    limit: int
    offset: int


class ListSectionsUseCase:
    def __init__(self, repo: LearningRepoProtocol) -> None:
        self._repo = repo

    def execute(self, req: ListSectionsInput) -> list[dict]:
        limit = max(1, min(req.limit, 100))
        offset = max(0, req.offset)
        return self._repo.list_released_sections(
            student_sub=req.student_sub,
            course_id=req.course_id,
            include_materials=req.include_materials,
            include_tasks=req.include_tasks,
            limit=limit,
            offset=offset,
        )
