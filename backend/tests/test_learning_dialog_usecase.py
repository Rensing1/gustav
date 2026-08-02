"""Unit tests for the framework-free dialog session use cases."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

from backend.learning.usecases.dialogs import DialogServiceUnavailable, DialogUseCases


@dataclass
class FakeRepo:
    session: dict[str, Any] = field(
        default_factory=lambda: {
            "id": "session-1",
            "status": "active",
            "response_mode": "free_text",
            "max_rounds": 2,
            "round_count": 0,
            "closing_prompt_md": None,
            "initial_starters": [],
            "initial_generation_status": "completed",
            "turns": [],
        }
    )
    failed: list[tuple[str, str]] = field(default_factory=list)
    usage_events: list[Any] = field(default_factory=list)
    completion_calls: int = 0

    def start_or_resume(self, **_kwargs: Any) -> dict[str, Any]:
        return dict(self.session)

    def set_initial_starters(self, **kwargs: Any) -> dict[str, Any]:
        self.session["initial_starters"] = list(kwargs["starters"])
        self.session["initial_generation_status"] = "completed"
        return dict(self.session)

    def claim_initial_starters(self, **_kwargs: Any) -> bool:
        self.session["initial_generation_status"] = "generating"
        return True

    def fail_initial_starters(self, **_kwargs: Any) -> None:
        self.session["initial_generation_status"] = "failed"

    def get_session(self, **_kwargs: Any) -> dict[str, Any]:
        return dict(self.session)

    def begin_turn(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "id": "turn-1",
            "status": "generating",
            "round_nr": self.session["round_count"] + 1,
            "student_message": kwargs["student_message"],
            "starter_text": kwargs.get("starter_text"),
            "starter_source": kwargs.get("starter_source"),
            "generation_attempts": 1,
        }

    def begin_retry(self, **_kwargs: Any) -> dict[str, Any]:
        return {
            "id": "turn-1",
            "status": "generating",
            "round_nr": 1,
            "student_message": "Meine Antwort",
            "starter_text": None,
            "starter_source": None,
            "generation_attempts": 2,
        }

    def generation_context(self, **_kwargs: Any) -> dict[str, Any]:
        return {
            "role_md": "Bleibe in deiner Rolle.",
            "learning_goal_md": "Argumentieren",
            "teacher_context_md": "Unterrichtskontext",
            "instruction_md": "Diskutiere.",
            "partner_name": "Sokrates",
            "opening_message_md": "Was denkst du?",
            "response_mode": self.session["response_mode"],
            "max_rounds": self.session["max_rounds"],
            "turns": [],
        }

    def complete_turn(self, **kwargs: Any) -> dict[str, Any]:
        self.session["round_count"] += 1
        turn = {
            "id": kwargs["turn_id"],
            "round_nr": self.session["round_count"],
            "status": "completed",
            "student_message": "Meine Antwort",
            "ai_message": kwargs["ai_message"],
            "next_starters": list(kwargs["next_starters"]),
        }
        self.session["turns"] = [turn]
        return dict(self.session)

    def fail_turn(self, **kwargs: Any) -> None:
        self.failed.append((kwargs["turn_id"], kwargs["error_code"]))

    def record_usage_events(self, **kwargs: Any) -> None:
        self.usage_events.extend(kwargs["events"])

    def complete_session(self, **kwargs: Any) -> dict[str, Any]:
        self.completion_calls += 1
        self.session["status"] = "completed"
        self.session["closing_answer_md"] = kwargs.get("closing_answer_md")
        return {
            "session": dict(self.session),
            "submission": {"id": "submission-1", "kind": "dialog", "intent": "submit", "attempt_nr": 1},
        }

    def abandon_session(self, **_kwargs: Any) -> dict[str, Any]:
        self.session["status"] = "abandoned"
        return dict(self.session)


@dataclass
class FakeGenerator:
    fail: bool = False

    def initial_starters(self, **_kwargs: Any) -> list[str]:
        if self.fail:
            raise RuntimeError("provider detail must not escape")
        return ["Ich denke, dass …"]

    def partner_reply(self, **_kwargs: Any) -> dict[str, Any]:
        if self.fail:
            raise RuntimeError("provider detail must not escape")
        return {"message": "Warum denkst du das?", "starters": ["Ein Grund ist …"]}


def _usecases(repo: FakeRepo | None = None, generator: FakeGenerator | None = None) -> tuple[DialogUseCases, FakeRepo]:
    actual_repo = repo or FakeRepo()
    return DialogUseCases(actual_repo, generator or FakeGenerator()), actual_repo


def test_free_text_start_does_not_call_model() -> None:
    class NoCalls(FakeGenerator):
        def initial_starters(self, **_kwargs: Any) -> list[str]:
            raise AssertionError("free text start must not call the model")

    usecases, _repo = _usecases(generator=NoCalls())

    session = usecases.start(course_id="course-1", task_id="task-1", student_sub="student-1")

    assert session["status"] == "active"
    assert session["initial_starters"] == []


def test_hybrid_start_generates_and_persists_first_starters() -> None:
    repo = FakeRepo()
    repo.session.update({"response_mode": "hybrid", "initial_generation_status": "pending"})
    usecases, _repo = _usecases(repo=repo)

    session = usecases.start(course_id="course-1", task_id="task-1", student_sub="student-1")

    assert session["initial_starters"] == ["Ich denke, dass …"]


def test_send_turn_persists_reply_and_starter_provenance() -> None:
    usecases, repo = _usecases()

    session = usecases.send_turn(
        course_id="course-1",
        task_id="task-1",
        session_id="session-1",
        student_sub="student-1",
        student_message="  Meine Antwort  ",
        idempotency_key="turn-key",
        starter_text="Ich denke, dass …",
        starter_source="initial",
    )

    assert session["round_count"] == 1
    assert session["turns"][0]["ai_message"] == "Warum denkst du das?"
    assert session["turns"][0]["next_starters"] == []
    assert repo.failed == []


def test_last_allowed_turn_has_reply_but_no_more_starters() -> None:
    repo = FakeRepo()
    repo.session["round_count"] = 1
    usecases, _repo = _usecases(repo=repo)

    session = usecases.send_turn(
        course_id="course-1",
        task_id="task-1",
        session_id="session-1",
        student_sub="student-1",
        student_message="Letzte Antwort",
        idempotency_key="last",
    )

    assert session["round_count"] == 2
    assert session["turns"][0]["ai_message"]
    assert session["turns"][0]["next_starters"] == []


def test_provider_failure_keeps_turn_retryable_and_exposes_stable_error() -> None:
    usecases, repo = _usecases(generator=FakeGenerator(fail=True))

    with pytest.raises(DialogServiceUnavailable, match="dialog_ai_unavailable"):
        usecases.send_turn(
            course_id="course-1",
            task_id="task-1",
            session_id="session-1",
            student_sub="student-1",
            student_message="Meine Antwort",
            idempotency_key="failure",
        )

    assert repo.failed == [("turn-1", "dialog_ai_unavailable")]


def test_invalid_model_output_marks_content_free_usage_as_failed() -> None:
    class InvalidOutputGenerator(FakeGenerator):
        def partner_reply(self, **_kwargs: Any) -> dict[str, Any]:
            return {"message": "", "starters": []}

        def pop_usage_events(self) -> list[Any]:
            return [SimpleNamespace(error_code=None)]

    usecases, repo = _usecases(generator=InvalidOutputGenerator())

    with pytest.raises(DialogServiceUnavailable, match="dialog_ai_unavailable"):
        usecases.send_turn(
            course_id="course-1",
            task_id="task-1",
            session_id="session-1",
            student_sub="student-1",
            student_message="Meine Antwort",
            idempotency_key="invalid-output",
        )

    assert len(repo.usage_events) == 1
    assert repo.usage_events[0].error_code == "dialog_ai_unavailable"


@pytest.mark.parametrize("message", ["", "   ", "x" * 2001])
def test_student_message_is_bounded(message: str) -> None:
    usecases, _repo = _usecases()

    with pytest.raises(ValueError, match="invalid_dialog_message"):
        usecases.send_turn(
            course_id="course-1",
            task_id="task-1",
            session_id="session-1",
            student_sub="student-1",
            student_message=message,
            idempotency_key="key",
        )


def test_complete_requires_closing_answer_when_prompt_exists() -> None:
    repo = FakeRepo()
    repo.session.update({"round_count": 1, "closing_prompt_md": "Fasse zusammen."})
    usecases, _repo = _usecases(repo=repo)

    with pytest.raises(ValueError, match="closing_answer_required"):
        usecases.complete(
            course_id="course-1",
            task_id="task-1",
            session_id="session-1",
            student_sub="student-1",
            closing_answer_md=" ",
            idempotency_key="complete-1",
        )

    assert repo.completion_calls == 0


def test_complete_creates_one_final_dialog_submission() -> None:
    repo = FakeRepo()
    repo.session["round_count"] = 1
    usecases, _repo = _usecases(repo=repo)

    result = usecases.complete(
        course_id="course-1",
        task_id="task-1",
        session_id="session-1",
        student_sub="student-1",
        closing_answer_md=None,
        idempotency_key="complete-1",
    )

    assert result["submission"]["kind"] == "dialog"
    assert result["submission"]["intent"] == "submit"
    assert repo.completion_calls == 1
