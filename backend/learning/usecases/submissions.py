from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from backend.learning.repo_db import SubmissionInput


class LearningSubmissionRepoProtocol(Protocol):
    def create_submission(self, data: SubmissionInput) -> dict:
        ...

    def list_submissions(
        self,
        *,
        student_sub: str,
        course_id: str,
        task_id: str,
        limit: int,
        offset: int,
    ) -> list[dict]:
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
        """Create a submission attempt for a task and return its record.

        Intent:
            Provide a minimal, framework‑free boundary for creating student
            submissions. All DB/RLS and concurrency concerns live in the repo.

        Parameters:
            req: Input containing path context (course_id, task_id), caller
                 identity (student_sub), payload kind and optional storage
                 metadata, and an optional Idempotency‑Key.

        Behavior:
            - Delegates to the repository which enforces membership, visibility
              and `max_attempts` via DB helpers and RLS.
            - Returns the inserted or idempotently reused submission.

        Permissions:
            Caller must be an enrolled student in the course with access to the
            released task (enforced at the DB boundary via RLS and helper functions).
        """
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


@dataclass
class ListSubmissionsInput:
    course_id: str
    task_id: str
    student_sub: str
    limit: int
    offset: int


class ListSubmissionsUseCase:
    def __init__(self, repo: LearningSubmissionRepoProtocol) -> None:
        self._repo = repo

    def execute(self, req: ListSubmissionsInput) -> list[dict]:
        """Return the student's submissions for a task with safe pagination.

        Intent:
            Encapsulate pagination bounds and stay unaware of FastAPI/HTTP.

        Behavior:
            - Clamp limit to 1..100 and offset to >= 0.
            - Delegate to the repository which enforces membership + visibility.

        Permissions:
            Same as create: caller must be an enrolled student with visibility
            to the released task. Violations surface as PermissionError/LookupError.
        """
        limit = max(1, min(req.limit, 100))
        offset = max(0, req.offset)
        return self._repo.list_submissions(
            student_sub=req.student_sub,
            course_id=req.course_id,
            task_id=req.task_id,
            limit=limit,
            offset=offset,
        )
