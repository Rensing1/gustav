"""
Structured DSPy feedback program tests (no real LLM calls).

Goal:
    Verify that the feedback orchestrator forwards task context to the
    structured runner functions and returns contract-compliant output.
"""

from __future__ import annotations

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
    monkeypatch.setitem(sys.modules, "dspy", SimpleNamespace(__version__="3.0.3"))
    programs = __import__("importlib").import_module("backend.learning.adapters.dspy.programs")

    def fake_no_criteria(*, teacher_context_md=None, **_kwargs):
        assert teacher_context_md == "Kontext"
        return "**Das ist dir gut gelungen:** A.\n\n**Das kannst du besser:** B."

    monkeypatch.setattr(programs, "run_feedback_no_criteria", fake_no_criteria, raising=False)

    mod = __import__("importlib").import_module("backend.learning.adapters.dspy.feedback_program")
    result = mod.analyze_feedback(text_md="Antwort", criteria=[], teacher_context_md="Kontext")  # type: ignore[attr-defined]
    assert result.analysis_json == {}
    assert result.parse_status == "skipped"
