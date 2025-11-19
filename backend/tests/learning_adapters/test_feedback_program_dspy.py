"""
Unit tests for the DSPy feedback program (criteria.v2).

Goal:
- Ensure the DSPy path returns a valid criteria.v2 structure.
- Enforce criterion-specific explanations (contains criterion name).
- Define behavior for empty criteria (overall score = 0, empty list).

Approach:
- Simulate DSPy presence by inserting a dummy module into sys.modules.
- Call the program function directly (no Ollama, no network).
"""

from __future__ import annotations

import sys
import json
import builtins
from importlib import import_module
from types import SimpleNamespace

import pytest


def _install_fake_dspy(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_dspy = SimpleNamespace(__version__="0.0-test")
    monkeypatch.setitem(sys.modules, "dspy", fake_dspy)


def _uninstall_fake_dspy(monkeypatch: pytest.MonkeyPatch) -> None:
    if "dspy" in sys.modules:
        monkeypatch.delitem(sys.modules, "dspy", raising=False)


def test_program_raises_when_dspy_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _uninstall_fake_dspy(monkeypatch)

    original_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "dspy":
            raise ImportError("dspy intentionally hidden for test")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    prog = import_module("backend.learning.adapters.dspy.feedback_program")
    with pytest.raises(ImportError):
        prog.analyze_feedback(text_md="# Text", criteria=["Inhalt"])  # type: ignore[arg-type]


def test_program_returns_v2_with_ranges_and_names(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_dspy(monkeypatch)
    prog = import_module("backend.learning.adapters.dspy.feedback_program")
    programs = import_module("backend.learning.adapters.dspy.programs")

    def fake_run_structured_analysis(*, text_md: str, criteria, **_kwargs):
        return {
            "schema": "criteria.v2",
            "score": 4,
            "criteria_results": [
                {"criterion": "Inhalt", "max_score": 10, "score": 8, "explanation_md": "Inhalt stärkt Aufbau"},
                {"criterion": "Struktur", "max_score": 10, "score": 6, "explanation_md": "Struktur klar"},
            ],
        }

    def fake_run_structured_feedback(*, text_md: str, criteria, analysis_json, **_kwargs):
        assert analysis_json["criteria_results"][0]["criterion"] == "Inhalt"
        return "**LLM**\n\n- Inhalt stark."

    monkeypatch.setattr(programs, "run_structured_analysis", fake_run_structured_analysis, raising=False)
    monkeypatch.setattr(programs, "run_structured_feedback", fake_run_structured_feedback, raising=False)

    result = prog.analyze_feedback(  # type: ignore[attr-defined]
        text_md="# Ein kurzer Text", criteria=["Inhalt", "Struktur"]
    )

    assert isinstance(result.feedback_md, str) and result.feedback_md.strip() != ""
    assert result.analysis_json.get("schema") == "criteria.v2"

    items = result.analysis_json.get("criteria_results") or []
    assert len(items) == 2
    for crit_name, item in zip(["Inhalt", "Struktur"], items):
        assert item["criterion"] == crit_name
        assert item["max_score"] == 10
        assert 0 <= int(item["score"]) <= 10
        assert crit_name in item["explanation_md"]  # name appears in explanation

    overall = int(result.analysis_json.get("score", -1))
    assert 0 <= overall <= 5


def test_program_with_empty_criteria_is_graceful(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_dspy(monkeypatch)
    prog = import_module("backend.learning.adapters.dspy.feedback_program")
    programs = import_module("backend.learning.adapters.dspy.programs")

    def fake_structured_feedback(*, text_md: str, criteria, analysis_json, **_kwargs):
        assert criteria == []
        assert analysis_json.schema == "criteria.v2"
        return "Eine kurze Rückmeldung im Fließtext."

    monkeypatch.setattr(programs, "run_structured_feedback", fake_structured_feedback, raising=False)
    result = prog.analyze_feedback(  # type: ignore[attr-defined]
        text_md="# Nur Text", criteria=[]
    )

    assert isinstance(result.feedback_md, str) and result.feedback_md.strip() != ""
    # No structured analysis when no criteria are defined
    assert result.analysis_json == {}
