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
    from importlib import import_module

    prog = import_module("backend.learning.adapters.dspy.feedback_program")
    with pytest.raises(ImportError):
        prog.analyze_feedback(text_md="# Text", criteria=["Inhalt"])  # type: ignore[arg-type]


def test_program_returns_v2_with_ranges_and_names(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_dspy(monkeypatch)
    from importlib import import_module

    prog = import_module("backend.learning.adapters.dspy.feedback_program")
    feedback_md, analysis = prog.analyze_feedback(  # type: ignore[attr-defined]
        text_md="# Ein kurzer Text", criteria=["Inhalt", "Struktur"]
    )

    assert isinstance(feedback_md, str) and feedback_md.strip() != ""
    assert analysis.get("schema") == "criteria.v2"

    items = analysis.get("criteria_results") or []
    assert len(items) == 2
    for crit_name, item in zip(["Inhalt", "Struktur"], items):
        assert item["criterion"] == crit_name
        assert item["max_score"] == 10
        assert 0 <= int(item["score"]) <= 10
        assert crit_name in item["explanation_md"]  # name appears in explanation

    overall = int(analysis.get("score", -1))
    assert 0 <= overall <= 5


def test_program_with_empty_criteria_is_graceful(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_dspy(monkeypatch)
    from importlib import import_module

    prog = import_module("backend.learning.adapters.dspy.feedback_program")
    feedback_md, analysis = prog.analyze_feedback(  # type: ignore[attr-defined]
        text_md="# Nur Text", criteria=[]
    )

    assert isinstance(feedback_md, str) and feedback_md.strip() != ""
    assert analysis.get("schema") == "criteria.v2"
    assert analysis.get("criteria_results") == []
    assert analysis.get("score") == 0

