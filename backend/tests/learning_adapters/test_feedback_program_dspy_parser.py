"""
Parser/Normalization tests for DSPy Feedback program (criteria.v2).

We monkeypatch the program's internal `_run_model` to simulate model outputs
and verify that `_parse` and normalization produce robust `criteria.v2` data:
- Accepts valid JSON with minor field name variations.
- Clamps scores into valid ranges and fills missing criteria.
- Falls back to deterministic default structure on malformed JSON.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest


def _install_fake_dspy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "dspy", SimpleNamespace(__version__="0.0-test"))


def _uninstall_fake_dspy(monkeypatch: pytest.MonkeyPatch) -> None:
    if "dspy" in sys.modules:
        monkeypatch.delitem(sys.modules, "dspy", raising=False)


def test_parser_accepts_variants_and_clamps(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_dspy(monkeypatch)
    from importlib import import_module

    mod = import_module("backend.learning.adapters.dspy.feedback_program")

    # Simulate a model returning variant field names and out-of-range values.
    raw = (
        "{\n"
        "  \"schema\": \"criteria.v2\",\n"
        "  \"score\": 9,\n"  # out of range → clamp to 5
        "  \"criteria\": [\n"
        "    {\"name\": \"Inhalt\", \"max\": 10, \"score\": 11, \"explanation\": \"gut\"},\n"
        "    {\"name\": \"Struktur\", \"max\": 8, \"score\": -2, \"explanation_md\": \"verbesserbar\"}\n"
        "  ]\n"
        "}\n"
    )

    monkeypatch.setattr(mod, "_run_model", lambda **_: raw)  # type: ignore[attr-defined]

    feedback_md, analysis = mod.analyze_feedback(  # type: ignore[attr-defined]
        text_md="# Text", criteria=["Inhalt", "Struktur"]
    )
    assert isinstance(feedback_md, str) and feedback_md.strip()
    assert analysis.get("schema") == "criteria.v2"
    assert analysis.get("score") == 5  # clamped

    items = analysis.get("criteria_results")
    assert len(items) == 2

    a, b = items[0], items[1]
    assert a["criterion"] == "Inhalt" and a["max_score"] == 10 and a["score"] == 10
    assert b["criterion"] == "Struktur" and b["max_score"] == 8 and b["score"] == 0
    # Explanations include criterion name for clarity
    assert "Inhalt" in a["explanation_md"]
    assert "Struktur" in b["explanation_md"]


def test_parser_fills_missing_criteria_and_defaults_on_malformed(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_dspy(monkeypatch)
    from importlib import import_module

    mod = import_module("backend.learning.adapters.dspy.feedback_program")

    # First case: only one criterion present in JSON → fill the other using defaults.
    raw_one = (
        "{\n"
        "  \"criteria_results\": [ { \"criterion\": \"Inhalt\", \"max_score\": 10, \"score\": 4, \"explanation_md\": \"ok\" } ]\n"
        "}\n"
    )
    monkeypatch.setattr(mod, "_run_model", lambda **_: raw_one)  # type: ignore[attr-defined]

    _, analysis = mod.analyze_feedback(  # type: ignore[attr-defined]
        text_md="# Text", criteria=["Inhalt", "Struktur"]
    )
    items = analysis.get("criteria_results")
    assert len(items) == 2
    names = {it["criterion"] for it in items}
    assert names == {"Inhalt", "Struktur"}

    # Second case: malformed JSON → all defaults used (deterministic fallbacks)
    monkeypatch.setattr(mod, "_run_model", lambda **_: "not json at all")  # type: ignore[attr-defined]
    _, analysis2 = mod.analyze_feedback(  # type: ignore[attr-defined]
        text_md="# Text", criteria=["Inhalt", "Struktur"]
    )
    assert analysis2.get("schema") == "criteria.v2"
    items2 = analysis2.get("criteria_results")
    assert len(items2) == 2
    assert all("criterion" in it and "score" in it for it in items2)

