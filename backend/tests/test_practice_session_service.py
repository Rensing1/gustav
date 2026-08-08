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
