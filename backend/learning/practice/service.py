"""Framework-independent practice-session use cases.

Why:
    HTTP handlers should only translate authentication, payloads and stable
    errors. Selection limits and session transitions belong to the Learning
    domain so every adapter observes the same rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Protocol, Sequence


MAX_SELECTED_STACKS = 50
MAX_SESSION_ITEMS = 1000


class ActivePracticeSessionError(RuntimeError):
    """Signal that a learner already owns an active session."""

    def __init__(self, session_id: str) -> None:
        super().__init__("practice_session_active")
        self.session_id = session_id


class PracticeRepoProtocol(Protocol):
    def list_stacks(self, *, student_sub: str) -> list[dict]: ...

    def create_session(
        self,
        *,
        student_sub: str,
        mode: str,
        stacks: list[dict[str, str]],
        rng: random.Random,
        max_items: int,
    ) -> dict: ...

    def get_active_session(self, *, student_sub: str) -> dict | None: ...

    def get_session(self, *, student_sub: str, session_id: str) -> dict | None: ...

    def continue_session(self, *, student_sub: str, session_id: str) -> dict | None: ...

    def skip_item(self, *, student_sub: str, session_id: str, item_id: str) -> dict | None: ...

    def end_session(self, *, student_sub: str, session_id: str) -> dict | None: ...


def _selection(stacks: object) -> list[dict[str, str]]:
    if isinstance(stacks, (str, bytes)) or not isinstance(stacks, Sequence):
        raise ValueError("invalid_practice_stacks")
    if not stacks:
        raise ValueError("invalid_practice_stacks")
    if len(stacks) > MAX_SELECTED_STACKS:
        raise ValueError("too_many_stacks")

    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in stacks:
        if not isinstance(item, dict):
            raise ValueError("invalid_practice_stacks")
        course_id = str(item.get("course_id") or "").strip()
        module_id = str(item.get("practice_module_id") or "").strip()
        if not course_id or not module_id:
            raise ValueError("invalid_practice_stacks")
        key = (course_id, module_id)
        if key in seen:
            continue
        seen.add(key)
        result.append({"course_id": course_id, "practice_module_id": module_id})
    return result


@dataclass
class PracticeService:
    """Coordinate learner-owned practice stacks and session transitions."""

    repo: PracticeRepoProtocol
    rng: random.Random = field(default_factory=random.SystemRandom)

    def list_stacks(self, student_sub: str) -> list[dict]:
        return self.repo.list_stacks(student_sub=student_sub)

    def create_session(self, student_sub: str, *, mode: object, stacks: object) -> dict:
        normalized_mode = str(mode or "").strip().lower()
        if normalized_mode not in {"due", "exam"}:
            raise ValueError("invalid_practice_mode")
        return self.repo.create_session(
            student_sub=student_sub,
            mode=normalized_mode,
            stacks=_selection(stacks),
            rng=self.rng,
            max_items=MAX_SESSION_ITEMS,
        )

    def get_active_session(self, student_sub: str) -> dict | None:
        return self.repo.get_active_session(student_sub=student_sub)

    def get_session(self, student_sub: str, session_id: str) -> dict:
        session = self.repo.get_session(student_sub=student_sub, session_id=session_id)
        if session is None:
            raise LookupError("practice_session_not_found")
        return session

    def continue_session(self, student_sub: str, session_id: str) -> dict:
        session = self.repo.continue_session(student_sub=student_sub, session_id=session_id)
        if session is None:
            raise LookupError("practice_session_not_found")
        return session

    def skip_item(self, student_sub: str, session_id: str, item_id: str) -> dict:
        session = self.repo.skip_item(student_sub=student_sub, session_id=session_id, item_id=item_id)
        if session is None:
            raise LookupError("practice_session_not_found")
        return session

    def end_session(self, student_sub: str, session_id: str) -> dict:
        session = self.repo.end_session(student_sub=student_sub, session_id=session_id)
        if session is None:
            raise LookupError("practice_session_not_found")
        return session
