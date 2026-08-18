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
            # Intentionally out-of-range to ensure normalization clamps.
            "score": 9,
            "criteria_results": [
                {"criterion": "Inhalt", "max_score": 10, "score": 11, "explanation_md": "Nachvollziehbar begründet."},
                {"criterion": "Struktur", "max_score": 10, "score": -1, "explanation_md": "Ansatz erkennbar."},
            ],
        }

    def fake_run_structured_feedback(*, text_md: str, criteria, analysis_json, **_kwargs):
        assert analysis_json["criteria_results"][0]["criterion"] == "Inhalt"
        return (
            "**Das ist Ihnen gut gelungen:** Sie haben zentrale Punkte verständlich erklärt.\n\n"
            "**Das können Sie noch besser:** Achten Sie beim nächsten Mal stärker auf eine klare Gliederung."
        )

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
        assert isinstance(item["explanation_md"], str) and item["explanation_md"].strip()

    overall = int(result.analysis_json.get("score", -1))
    assert 0 <= overall <= 5
    assert "**Das ist Ihnen gut gelungen:**" in result.feedback_md
    assert "**Das können Sie noch besser:**" in result.feedback_md


def test_program_raises_when_structured_pipeline_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail-fast: do not fall back to legacy runners when structured DSPy fails."""
    _install_fake_dspy(monkeypatch)
    prog = import_module("backend.learning.adapters.dspy.feedback_program")
    programs = import_module("backend.learning.adapters.dspy.programs")

    monkeypatch.setattr(
        programs,
        "run_structured_analysis",
        lambda **_: (_ for _ in ()).throw(RuntimeError("structured_analysis_failed")),
        raising=False,
    )
    with pytest.raises(RuntimeError):
        prog.analyze_feedback(text_md="# Text", criteria=["Inhalt"])  # type: ignore[arg-type]


def test_program_with_empty_criteria_generates_feedback(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_dspy(monkeypatch)
    prog = import_module("backend.learning.adapters.dspy.feedback_program")
    programs = import_module("backend.learning.adapters.dspy.programs")

    def fake_feedback_no_criteria(*, text_md: str, **_kwargs):
        return (
            "**Das ist Ihnen gut gelungen:** Sie haben sich erkennbar mit dem Thema beschäftigt.\n\n"
            "**Das können Sie noch besser:** Formulieren Sie Ihre Antwort beim nächsten Mal noch genauer."
        )

    monkeypatch.setattr(programs, "run_feedback_no_criteria", fake_feedback_no_criteria, raising=False)
    result = prog.analyze_feedback(  # type: ignore[attr-defined]
        text_md="# Nur Text", criteria=[]
    )

    assert isinstance(result.feedback_md, str) and result.feedback_md.strip() != ""
    # No structured analysis when no criteria are defined
    assert result.analysis_json == {}
