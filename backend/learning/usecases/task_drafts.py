"""Private working text, separate from immutable feedback and final submissions."""
from typing import Protocol


class TaskDraftRepository(Protocol):
    def read_task_draft(self, student_sub: str, course_id: str, task_id: str) -> dict | None: ...
    def save_task_draft(self, student_sub: str, course_id: str, task_id: str, text_body: str) -> dict: ...


class TaskDrafts:
    """Read/replace a learner's working text without starting assessment.

    Identity comes from the authenticated caller. The repository enforces active
    membership and released native learning tasks for both reads and writes.
    Empty text is a deliberate saved state; never trim or normalize Markdown.
    """
    def __init__(self, repository: TaskDraftRepository):
        self.repository = repository

    def read(self, student_sub: str, course_id: str, task_id: str) -> dict | None:
        return self.repository.read_task_draft(student_sub, course_id, task_id)

    def save(self, student_sub: str, course_id: str, task_id: str, payload: object) -> dict:
        if not isinstance(payload, dict) or set(payload) != {'text_body'}:
            raise ValueError('invalid_input')
        text = payload['text_body']
        if not isinstance(text, str) or len(text) > 65536 or '\x00' in text:
            raise ValueError('invalid_input')
        return self.repository.save_task_draft(student_sub, course_id, task_id, text)
