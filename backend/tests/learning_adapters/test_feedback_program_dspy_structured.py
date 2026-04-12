"""
Structured DSPy feedback program tests (no real LLM calls).

Goal:
    Verify that the feedback orchestrator forwards task context to the
    structured runner functions and returns contract-compliant output.
"""

from __future__ import annotations

import logging
import sys
from types import SimpleNamespace

import pytest


def test_feedback_program_forwards_teacher_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "dspy", SimpleNamespace(__version__="3.0.3"))
    programs = __import__("importlib").import_module("backend.learning.adapters.dspy.programs")

    def fake_run_structured_analysis(*, teacher_instructions_md=None, teacher_context_md=None, **_kwargs):
        assert teacher_instructions_md == "Aufgabe"
        assert teacher_context_md == "Kontext"
        return {
            "schema": "criteria.v2",
            "score": 3,
            "criteria_results": [
                {"criterion": "Inhalt", "max_score": 10, "score": 6, "explanation_md": "ok"},
            ],
        }

    def fake_run_structured_feedback(*, analysis_json: dict, teacher_context_md=None, **_kwargs):
        assert analysis_json.get("schema") == "criteria.v2"
        assert teacher_context_md == "Kontext"
        return "**Das ist dir gut gelungen:** A.\n\n**Das kannst du besser:** B."

    monkeypatch.setattr(programs, "run_structured_analysis", fake_run_structured_analysis, raising=False)
    monkeypatch.setattr(programs, "run_structured_feedback", fake_run_structured_feedback, raising=False)

    mod = __import__("importlib").import_module("backend.learning.adapters.dspy.feedback_program")
    result = mod.analyze_feedback(  # type: ignore[attr-defined]
        text_md="Antwort",
        criteria=["Inhalt"],
        teacher_instructions_md="Aufgabe",
        teacher_context_md="Kontext",
    )
    assert result.analysis_json.get("schema") == "criteria.v2"
    assert "**Das ist dir gut gelungen:**" in result.feedback_md
    assert "**Das kannst du besser:**" in result.feedback_md


def test_feedback_program_empty_criteria_uses_no_criteria_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: list[dict] = []

    class _FakeJsonAdapter:
        pass

    class _FakeDspy:
        __version__ = "3.0.3"
        JSONAdapter = _FakeJsonAdapter

        @staticmethod
        def context(**kwargs):  # type: ignore[no-untyped-def]
            class _Ctx:
                def __enter__(self_inner):
                    observed.append(dict(kwargs))
                    return None

                def __exit__(self_inner, exc_type, exc, tb):
                    return False

            return _Ctx()

    monkeypatch.setitem(sys.modules, "dspy", _FakeDspy())
    programs = __import__("importlib").import_module("backend.learning.adapters.dspy.programs")

    def fake_no_criteria(*, teacher_context_md=None, **_kwargs):
        assert teacher_context_md == "Kontext"
        return "**Das ist dir gut gelungen:** A.\n\n**Das kannst du besser:** B."

    monkeypatch.setattr(programs, "run_feedback_no_criteria", fake_no_criteria, raising=False)

    mod = __import__("importlib").import_module("backend.learning.adapters.dspy.feedback_program")
    result = mod.analyze_feedback(  # type: ignore[attr-defined]
        text_md="Antwort",
        criteria=[],
        teacher_context_md="Kontext",
        synthesis_lm=object(),
    )
    assert result.analysis_json == {}
    assert result.parse_status == "skipped"
    assert len(observed) == 1
    assert observed[0]["lm"] is not None


def test_feedback_program_retries_analysis_once_after_invalid_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "dspy", SimpleNamespace(__version__="3.0.3"))
    programs = __import__("importlib").import_module("backend.learning.adapters.dspy.programs")
    calls = {"analysis": 0, "repair": 0}

    def fake_run_structured_analysis(**_kwargs):
        calls["analysis"] += 1
        raise RuntimeError("invalid_analysis_json")

    def fake_run_structured_analysis_repair(*, repair_reason: str, **_kwargs):
        calls["repair"] += 1
        assert repair_reason == "invalid_analysis_json"
        return {
            "schema": "criteria.v2",
            "score": 3,
            "criteria_results": [
                {"criterion": "Inhalt", "max_score": 10, "score": 6, "explanation_md": "ok"},
            ],
        }

    def fake_run_structured_feedback(*, analysis_json: dict, **_kwargs):
        assert analysis_json.get("schema") == "criteria.v2"
        return "**Das ist dir gut gelungen:** A.\n\n**Das kannst du besser:** B."

    monkeypatch.setattr(programs, "run_structured_analysis", fake_run_structured_analysis, raising=False)
    monkeypatch.setattr(programs, "run_structured_analysis_repair", fake_run_structured_analysis_repair, raising=False)
    monkeypatch.setattr(programs, "run_structured_feedback", fake_run_structured_feedback, raising=False)

    mod = __import__("importlib").import_module("backend.learning.adapters.dspy.feedback_program")
    result = mod.analyze_feedback(  # type: ignore[attr-defined]
        text_md="Antwort",
        criteria=["Inhalt"],
        teacher_instructions_md="Aufgabe",
        teacher_context_md="Kontext",
    )

    assert calls == {"analysis": 1, "repair": 1}
    assert result.parse_status == "repaired_structured"


def test_feedback_program_raises_when_repair_attempt_is_still_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "dspy", SimpleNamespace(__version__="3.0.3"))
    programs = __import__("importlib").import_module("backend.learning.adapters.dspy.programs")

    monkeypatch.setattr(
        programs,
        "run_structured_analysis",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("invalid_analysis_json")),
        raising=False,
    )
    monkeypatch.setattr(
        programs,
        "run_structured_analysis_repair",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("invalid_analysis_json")),
        raising=False,
    )

    mod = __import__("importlib").import_module("backend.learning.adapters.dspy.feedback_program")
    with pytest.raises(RuntimeError, match="invalid_analysis_json"):
        mod.analyze_feedback(  # type: ignore[attr-defined]
            text_md="Antwort",
            criteria=["Inhalt"],
            teacher_instructions_md="Aufgabe",
            teacher_context_md="Kontext",
        )


def test_feedback_program_logs_stage_metadata(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setitem(sys.modules, "dspy", SimpleNamespace(__version__="3.0.3"))
    programs = __import__("importlib").import_module("backend.learning.adapters.dspy.programs")
    observability = __import__("importlib").import_module("backend.learning.adapters.dspy.json_observability")

    monkeypatch.setattr(
        programs,
        "run_structured_analysis",
        lambda **_kwargs: {
            "schema": "criteria.v2",
            "score": 3,
            "criteria_results": [
                {"criterion": "Inhalt", "max_score": 10, "score": 6, "explanation_md": "ok"},
            ],
        },
        raising=False,
    )
    monkeypatch.setattr(
        programs,
        "run_structured_feedback",
        lambda **_kwargs: "**Das ist dir gut gelungen:** A.\n\n**Das kannst du besser:** B.",
        raising=False,
    )

    metadata = iter(
        [
            {
                "stage": "analysis",
                "model": "openai/mistral-small-4",
                "provider": "openai",
                "response_format_mode": "json_schema",
                "reasoning_effort": "none",
            },
            {
                "stage": "synthesis",
                "model": "openai/mistral-small-4",
                "provider": "openai",
                "response_format_mode": "json_object_fallback",
                "reasoning_effort": "none",
            },
        ]
    )
    monkeypatch.setattr(observability, "pop_last_call_metadata", lambda: next(metadata, None))
    monkeypatch.setattr(observability, "build_json_adapter", lambda **_kwargs: object())

    mod = __import__("importlib").import_module("backend.learning.adapters.dspy.feedback_program")
    caplog.set_level(logging.INFO)
    mod.analyze_feedback(text_md="Antwort", criteria=["Inhalt"])  # type: ignore[attr-defined]

    messages = [record.getMessage() for record in caplog.records]
    assert any("learning.feedback.dspy_stage_completed" in message for message in messages)
    assert any("learning.feedback.dspy_response_format_fallback" in message for message in messages)
