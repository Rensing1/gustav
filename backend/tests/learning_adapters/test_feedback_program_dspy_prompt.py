import importlib
from typing import List

import pytest


@pytest.mark.anyio
def test_dspy_feedback_program_normalizes_structured_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Structured DSPy analysis is normalized to criteria.v2 (clamping + ordering)."""

    class _FakeDSPy:
        __version__ = "0.1-test"

    monkeypatch.setitem(__import__("sys").modules, "dspy", _FakeDSPy())

    mod = importlib.import_module("backend.learning.adapters.dspy.feedback_program")
    programs = importlib.import_module("backend.learning.adapters.dspy.programs")

    def fake_run_structured_analysis(*, text_md: str, criteria: list[str], **_kwargs):
        return {
            "schema": "criteria.v2",
            "score": "4.0",
            "criteria_results": [
                {"criterion": "Inhalt", "max_score": 10, "score": 11, "explanation_md": "gut"},
                {"criterion": "Darstellung", "max_score": 5, "score": -1, "explanation_md": "ok"},
            ],
        }

    def fake_run_structured_feedback(*, text_md: str, criteria: list[str], analysis_json, **_kwargs):
        assert criteria == ["Inhalt", "Darstellung"]
        return (
            "**Das ist dir gut gelungen:** Du hast zentrale Punkte verständlich erklärt.\n\n"
            "**Das kannst du besser:** Achte beim nächsten Mal stärker auf eine klare Gliederung."
        )

    monkeypatch.setattr(programs, "run_structured_analysis", fake_run_structured_analysis, raising=False)
    monkeypatch.setattr(programs, "run_structured_feedback", fake_run_structured_feedback, raising=False)

    result = mod.analyze_feedback(text_md="# Lösung\nText", criteria=["Inhalt", "Darstellung"])

    assert result.analysis_json["schema"] == "criteria.v2"
    assert 0 <= int(result.analysis_json["score"]) <= 5
    items = result.analysis_json["criteria_results"]
    assert isinstance(items, list) and len(items) == 2
    inhalt = next(i for i in items if i["criterion"] == "Inhalt")
    darst = next(i for i in items if i["criterion"] == "Darstellung")
    assert 0 <= inhalt["score"] <= inhalt["max_score"]
    assert 0 <= darst["score"] <= darst["max_score"]
    assert "**Das ist dir gut gelungen:**" in result.feedback_md
    assert "**Das kannst du besser:**" in result.feedback_md
