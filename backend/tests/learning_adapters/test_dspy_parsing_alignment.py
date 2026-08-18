"""
Tests for aligning DSPy structured outputs to expected criteria names by order.

Intent:
    If the model returns criteria_results with different names but in the
    correct order and count, we relabel them to the expected input names,
    preserving the scores and explanations. This avoids zeroed "stub" rows
    caused by strict name matching.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest


def test_feedback_program_aligns_items_by_order(monkeypatch: pytest.MonkeyPatch) -> None:
    # Pretend DSPy is importable (the program checks presence only).
    monkeypatch.setitem(sys.modules, "dspy", SimpleNamespace(__version__="3.0.3"))

    programs = __import__("importlib").import_module("backend.learning.adapters.dspy.programs")

    # Structured analysis returns two items in the correct order but with different names.
    monkeypatch.setattr(
        programs,
        "run_structured_analysis",
        lambda **_: {
            "schema": "criteria.v2",
            "score": 4,
            "criteria_results": [
                {"criterion": "Content", "max_score": 10, "score": 8, "explanation_md": "OK"},
                {"criterion": "Structure", "max_score": 10, "score": 6, "explanation_md": "OK"},
            ],
        },
        raising=False,
    )
    monkeypatch.setattr(
        programs,
        "run_structured_feedback",
        lambda **_: "**Das ist Ihnen gut gelungen:** A.\n\n**Das können Sie noch besser:** B.",
        raising=False,
    )

    mod = __import__("importlib").import_module("backend.learning.adapters.dspy.feedback_program")
    result = mod.analyze_feedback(text_md="x", criteria=["Inhalt", "Struktur"])  # type: ignore[attr-defined]

    items = result.analysis_json["criteria_results"]
    assert [i["criterion"] for i in items] == ["Inhalt", "Struktur"]
    assert [i["score"] for i in items] == [8, 6]
