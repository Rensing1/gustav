"""
Structured DSPy pipeline tests for Visual tasks (image → analysis → feedback).

Intent:
    Encode the contract for the Visual DSPy program:
      - It requires DSPy to be importable.
      - It calls the structured runners (analysis + feedback) that accept a
        visual input (data-URI image) instead of plain text.
      - It returns a `criteria.v2`-shaped analysis_json plus prose feedback.

Notes:
    These tests stay deterministic by monkeypatching the structured runners
    at `backend.learning.adapters.dspy.programs` (no real LM calls).
"""

from __future__ import annotations

import builtins
import importlib
import sys
from types import SimpleNamespace

import pytest


def _install_fake_dspy(monkeypatch: pytest.MonkeyPatch) -> None:
    # For this unit test we only need "import dspy" to succeed.
    monkeypatch.setitem(sys.modules, "dspy", SimpleNamespace(__version__="3.0.3"))


def _hide_dspy_import(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "dspy":
            raise ImportError("dspy intentionally hidden for test")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)


def test_visual_feedback_program_raises_when_dspy_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    if "dspy" in sys.modules:
        monkeypatch.delitem(sys.modules, "dspy", raising=False)
    _hide_dspy_import(monkeypatch)

    mod = importlib.import_module("backend.learning.adapters.dspy.visual_feedback_program")
    with pytest.raises(ImportError):
        _ = mod.analyze_visual_feedback(  # type: ignore[attr-defined]
            image_data_uri="data:image/png;base64,AA==",
            criteria=["K1"],
            teacher_instructions_md="Aufgabe",
            solution_hints_md=None,
        )


def test_visual_feedback_program_structured_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_dspy(monkeypatch)

    programs = importlib.import_module("backend.learning.adapters.dspy.programs")

    def fake_run_structured_visual_analysis(
        *,
        image_data_uri: str,
        criteria: list[str],
        teacher_instructions_md=None,
        solution_hints_md=None,
    ):
        assert image_data_uri.startswith("data:image/"), "visual pipeline must receive an image data URI"
        return {
            "schema": "criteria.v2",
            "score": 4,
            "criteria_results": [
                {"criterion": criteria[0], "max_score": 10, "score": 2, "explanation_md": "ok"},
                {"criterion": criteria[1], "max_score": 10, "score": 7, "explanation_md": "gut"},
            ],
        }

    def fake_run_structured_visual_feedback(
        *,
        image_data_uri: str,
        criteria: list[str],
        analysis_json: dict,
        teacher_instructions_md=None,
    ):
        assert image_data_uri.startswith("data:image/"), "visual feedback must receive an image data URI"
        assert analysis_json.get("schema") == "criteria.v2"
        return "Die Lösung ist insgesamt gut; beim ersten Kriterium noch genauer werden."

    monkeypatch.setattr(programs, "run_structured_visual_analysis", fake_run_structured_visual_analysis, raising=False)
    monkeypatch.setattr(programs, "run_structured_visual_feedback", fake_run_structured_visual_feedback, raising=False)

    mod = importlib.import_module("backend.learning.adapters.dspy.visual_feedback_program")
    result = mod.analyze_visual_feedback(  # type: ignore[attr-defined]
        image_data_uri="data:image/png;base64,AA==",
        criteria=["Inhalt", "Struktur"],
        teacher_instructions_md="Aufgabe",
        solution_hints_md="Hinweis",
    )

    assert result.parse_status == "parsed_structured"
    assert result.analysis_json.get("schema") == "criteria.v2"
    items = result.analysis_json.get("criteria_results")
    assert isinstance(items, list) and len(items) == 2
    assert items[0]["criterion"] == "Inhalt" and items[1]["criterion"] == "Struktur"
    assert "insgesamt" in result.feedback_md

