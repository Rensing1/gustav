"""
Structured DSPy pipeline tests (analysis → feedback) without real LLM calls.

We monkeypatch the DSPy Predict runner used by our programs so that:
- Analysis returns a structured object with `overall_score` and `criteria_results`.
- Feedback returns a prose string.

Expectations:
- The `analyze_feedback` function uses the structured path when available
  and sets `parse_status` accordingly ("parsed_structured").
- The returned `analysis_json` matches what the structured runner produced
  (subject to minor normalization like clamping and ordering).
"""

from __future__ import annotations

from types import SimpleNamespace

import importlib
import json
import pytest


@pytest.mark.anyio
async def test_structured_pipeline_passes_through_analysis_and_feedback(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    # Pretend DSPy is available and Predict returns our structured object.
    import sys
    monkeypatch.setitem(sys.modules, "dspy", SimpleNamespace(__version__="3.0.3"))

    # Inject structured analysis/feedback runners at the programs layer.
    programs = importlib.import_module("backend.learning.adapters.dspy.programs")

    def fake_run_structured_analysis(*, text_md: str, criteria: list[str], teacher_instructions_md=None, solution_hints_md=None):
        return {
            "schema": "criteria.v2",
            "score": 4,
            "criteria_results": [
                {"criterion": criteria[0], "max_score": 10, "score": 2, "explanation_md": "ok"},
                {"criterion": criteria[1], "max_score": 10, "score": 7, "explanation_md": "gut"},
            ],
        }

    def fake_run_structured_feedback(*, text_md: str, criteria: list[str], analysis_json: dict, teacher_instructions_md=None):
        # Return prose, not a list/bullets.
        return "Die Arbeit zeigt Stärken beim zweiten Kriterium; nächstes Mal Fokus auf das erste."

    monkeypatch.setattr(programs, "run_structured_analysis", fake_run_structured_analysis, raising=False)
    monkeypatch.setattr(programs, "run_structured_feedback", fake_run_structured_feedback, raising=False)

    # Block legacy single-phase path to ensure structured route is taken.
    mod = importlib.import_module("backend.learning.adapters.dspy.feedback_program")
    monkeypatch.setattr(
        mod,
        "_run_model",
        lambda **_: (_ for _ in ()).throw(AssertionError("legacy single-phase runner must not execute")),
        raising=False,
    )

    # Act
    result = mod.analyze_feedback(  # type: ignore[attr-defined]
        text_md="## Text", criteria=["Inhalt", "Struktur"], teacher_instructions_md="Aufgabe"
    )

    # Assert
    assert result.parse_status == "parsed_structured"
    assert result.analysis_json.get("schema") == "criteria.v2"
    items = result.analysis_json.get("criteria_results")
    assert len(items) == 2 and items[0]["criterion"] == "Inhalt" and items[1]["criterion"] == "Struktur"
    assert result.feedback_md and "Stärken" in result.feedback_md

