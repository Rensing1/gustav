from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from backend.learning.repo_db import SubmissionInput


class LearningSubmissionRepoProtocol(Protocol):
    def create_submission(self, data: SubmissionInput) -> dict:
        ...


@dataclass
class CreateSubmissionInput:
    course_id: str
    task_id: str
    student_sub: str
    kind: str
    text_body: Optional[str]
    storage_key: Optional[str]
    mime_type: Optional[str]
    size_bytes: Optional[int]
    sha256: Optional[str]
    idempotency_key: Optional[str]


class CreateSubmissionUseCase:
    def __init__(self, repo: LearningSubmissionRepoProtocol) -> None:
        self._repo = repo

    def execute(self, req: CreateSubmissionInput) -> dict:
        return self._repo.create_submission(
            SubmissionInput(
                course_id=req.course_id,
                task_id=req.task_id,
                student_sub=req.student_sub,
                kind=req.kind,
                text_body=req.text_body,
                storage_key=req.storage_key,
                mime_type=req.mime_type,
                size_bytes=req.size_bytes,
                sha256=req.sha256,
                idempotency_key=req.idempotency_key,
            )
        )
