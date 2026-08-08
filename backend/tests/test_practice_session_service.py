"""Use-case tests for practice session limits and deterministic snapshots."""

from __future__ import annotations

import random

import pytest

from backend.learning.practice.service import PracticeService


class Repo:
    def __init__(self) -> None:
        self.created: dict | None = None

    def create_session(self, **kwargs):
        self.created = kwargs
        return {"id": "session-1", "status": "active", "current_item": None}

    def create_native_attempt(self, **kwargs):
        self.created = kwargs
        return {"attempt_id": "attempt-1", "status": "pending"}

    def get_attempt(self, **kwargs):
        return None

    def reveal_solution(self, **kwargs):
        return None

    def issue_h5p_context(self, **kwargs):
        self.created = kwargs
        return {"practice_completion_token": "token", "context_id": "context"}

    def complete_h5p_attempt(self, **kwargs):
        self.created = kwargs
        return {"attempt_id": "attempt-h5p", "status": "completed"}


def test_create_session_rejects_more_than_fifty_stacks() -> None:
    stacks = [{"course_id": f"course-{index}", "practice_module_id": f"module-{index}"} for index in range(51)]
    with pytest.raises(ValueError, match="too_many_stacks"):
        PracticeService(Repo()).create_session("student-1", mode="due", stacks=stacks)


def test_create_session_deduplicates_selection_and_injects_random_source() -> None:
    repo = Repo()
    rng = random.Random(7)
    stacks = [
        {"course_id": "course-1", "practice_module_id": "module-1"},
        {"course_id": "course-1", "practice_module_id": "module-1"},
        {"course_id": "course-2", "practice_module_id": "module-2"},
    ]

    PracticeService(repo, rng=rng).create_session("student-1", mode="exam", stacks=stacks)

    assert repo.created is not None
    assert repo.created["student_sub"] == "student-1"
    assert repo.created["mode"] == "exam"
    assert repo.created["stacks"] == [stacks[0], stacks[2]]
    assert repo.created["rng"] is rng


@pytest.mark.parametrize("mode", ["", "all", None])
def test_create_session_rejects_unknown_mode(mode: object) -> None:
    with pytest.raises(ValueError, match="invalid_practice_mode"):
        PracticeService(Repo()).create_session(
            "student-1",
            mode=mode,
            stacks=[{"course_id": "course-1", "practice_module_id": "module-1"}],
        )


def test_native_attempt_requires_nonempty_answer_and_idempotency_key() -> None:
    service = PracticeService(Repo())
    with pytest.raises(ValueError, match="missing_idempotency_key"):
        service.create_native_attempt(
            "student-1", "session-1", "item-1", answer_text="Antwort", idempotency_key=""
        )
    with pytest.raises(ValueError, match="invalid_practice_answer"):
        service.create_native_attempt(
            "student-1", "session-1", "item-1", answer_text="   ", idempotency_key="key-1"
        )


def test_native_attempt_normalizes_input_before_repository_call() -> None:
    repo = Repo()
    result = PracticeService(repo).create_native_attempt(
        "student-1",
        "session-1",
        "item-1",
        answer_text="  Meine Antwort  ",
        idempotency_key="  key-1  ",
    )
    assert result == {"attempt_id": "attempt-1", "status": "pending"}
    assert repo.created == {
        "student_sub": "student-1",
        "session_id": "session-1",
        "item_id": "item-1",
        "answer_text": "Meine Antwort",
        "idempotency_key": "key-1",
    }


def test_h5p_completion_rejects_invalid_scores_or_missing_token() -> None:
    service = PracticeService(Repo())
    with pytest.raises(ValueError, match="missing_practice_completion_token"):
        service.complete_h5p_attempt(
            "student-1", "session-1", "item-1", score_raw=1, score_max=1, completion_token=""
        )
    with pytest.raises(ValueError, match="invalid_h5p_score"):
        service.complete_h5p_attempt(
            "student-1", "session-1", "item-1", score_raw=2, score_max=1, completion_token="token"
        )
