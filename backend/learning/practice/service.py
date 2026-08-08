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

    def create_native_attempt(
        self, *, student_sub: str, session_id: str, item_id: str,
        answer_text: str, idempotency_key: str
    ) -> dict: ...

    def get_attempt(self, *, student_sub: str, attempt_id: str) -> dict | None: ...

    def reveal_solution(
        self, *, student_sub: str, session_id: str, item_id: str
    ) -> dict | None: ...

    def issue_h5p_context(
        self, *, student_sub: str, session_id: str, item_id: str
    ) -> dict | None: ...

    def complete_h5p_attempt(
        self, *, student_sub: str, session_id: str, item_id: str,
        score_raw: int, score_max: int, completion_token: str
    ) -> dict: ...


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

    def create_native_attempt(
        self,
        student_sub: str,
        session_id: str,
        item_id: str,
        *,
        answer_text: object,
        idempotency_key: object,
    ) -> dict:
        answer = str(answer_text or "").strip()
        key = str(idempotency_key or "").strip()
        if not key:
            raise ValueError("missing_idempotency_key")
        if len(key) > 128:
            raise ValueError("invalid_idempotency_key")
        if not answer:
            raise ValueError("invalid_practice_answer")
        return self.repo.create_native_attempt(
            student_sub=student_sub,
            session_id=session_id,
            item_id=item_id,
            answer_text=answer,
            idempotency_key=key,
        )

    def get_attempt(self, student_sub: str, attempt_id: str) -> dict:
        attempt = self.repo.get_attempt(student_sub=student_sub, attempt_id=attempt_id)
        if attempt is None:
            raise LookupError("practice_attempt_not_found")
        return attempt

    def reveal_solution(self, student_sub: str, session_id: str, item_id: str) -> dict:
        solution = self.repo.reveal_solution(
            student_sub=student_sub, session_id=session_id, item_id=item_id
        )
        if solution is None:
            raise LookupError("practice_session_not_found")
        return solution

    def issue_h5p_context(self, student_sub: str, session_id: str, item_id: str) -> dict:
        context = self.repo.issue_h5p_context(
            student_sub=student_sub, session_id=session_id, item_id=item_id
        )
        if context is None:
            raise LookupError("practice_session_not_found")
        return context

    def complete_h5p_attempt(
        self,
        student_sub: str,
        session_id: str,
        item_id: str,
        *,
        score_raw: object,
        score_max: object,
        completion_token: object,
    ) -> dict:
        token = str(completion_token or "").strip()
        if not token:
            raise ValueError("missing_practice_completion_token")
        if isinstance(score_raw, bool) or isinstance(score_max, bool):
            raise ValueError("invalid_h5p_score")
        try:
            raw, maximum = int(score_raw), int(score_max)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_h5p_score") from exc
        if raw < 0 or maximum <= 0 or raw > maximum:
            raise ValueError("invalid_h5p_score")
        return self.repo.complete_h5p_attempt(
            student_sub=student_sub,
            session_id=session_id,
            item_id=item_id,
            score_raw=raw,
            score_max=maximum,
            completion_token=token,
        )
