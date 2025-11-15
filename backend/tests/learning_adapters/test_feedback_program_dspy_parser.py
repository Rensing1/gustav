"""
Parser/Normalization tests for DSPy Feedback program (criteria.v2).

We monkeypatch the program's internal `_run_model` to simulate model outputs
and verify that `_parse` and normalization produce robust `criteria.v2` data:
- Accepts valid JSON with minor field name variations.
- Clamps scores into valid ranges and fills missing criteria.
- Falls back to deterministic default structure on malformed JSON.
"""

from __future__ import annotations

import json
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
    monkeypatch.setattr(mod, "_run_feedback_model", lambda **_: "**Stub Feedback**", raising=False)  # type: ignore[attr-defined]

    result = mod.analyze_feedback(  # type: ignore[attr-defined]
        text_md="# Text", criteria=["Inhalt", "Struktur"]
    )
    assert result.feedback_md.strip()
    assert result.analysis_json.get("schema") == "criteria.v2"
    assert result.analysis_json.get("score") == 5  # clamped

    items = result.analysis_json.get("criteria_results")
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
    monkeypatch.setattr(mod, "_run_feedback_model", lambda **_: "**Stub Feedback**", raising=False)  # type: ignore[attr-defined]

    result = mod.analyze_feedback(  # type: ignore[attr-defined]
        text_md="# Text", criteria=["Inhalt", "Struktur"]
    )
    items = result.analysis_json.get("criteria_results")
    assert len(items) == 2
    names = {it["criterion"] for it in items}
    assert names == {"Inhalt", "Struktur"}
    # Missing criterion should default to score 0 for KISS/no-evidence behavior
    filled = {it["criterion"]: it for it in items}
    assert filled["Struktur"]["score"] == 0

    # Second case: malformed JSON → all defaults used (deterministic fallbacks)
    monkeypatch.setattr(mod, "_run_model", lambda **_: "not json at all")  # type: ignore[attr-defined]
    monkeypatch.setattr(mod, "_run_feedback_model", lambda **_: "**Stub Feedback**", raising=False)  # type: ignore[attr-defined]
    result2 = mod.analyze_feedback(  # type: ignore[attr-defined]
        text_md="# Text", criteria=["Inhalt", "Struktur"]
    )
    assert result2.analysis_json.get("schema") == "criteria.v2"
    items2 = result2.analysis_json.get("criteria_results")
    assert len(items2) == 2
    assert all("criterion" in it and "score" in it for it in items2)
    # Deterministic fallback: all items default to 0
    assert all(it["score"] == 0 for it in items2)


def test_parser_passes_through_model_feedback(monkeypatch: pytest.MonkeyPatch) -> None:
    """DSPy feedback text must propagate to callers instead of stub markdown."""
    _install_fake_dspy(monkeypatch)
    from importlib import import_module

    mod = import_module("backend.learning.adapters.dspy.feedback_program")

    payload = {
        "schema": "criteria.v2",
        "score": 4,
        "criteria_results": [
            {"criterion": "Inhalt", "max_score": 10, "score": 8, "explanation_md": "klar"},
        ],
        "feedback_md": "**Lob**\n\n- Gute Argumente.",
    }

    monkeypatch.setattr(mod, "_run_model", lambda **_: json.dumps(payload), raising=False)  # type: ignore[attr-defined]
    monkeypatch.setattr(mod, "_run_feedback_model", lambda **_: payload["feedback_md"], raising=False)  # type: ignore[attr-defined]

    result = mod.analyze_feedback(  # type: ignore[attr-defined]
        text_md="# Text", criteria=["Inhalt"]
    )
    assert result.feedback_md == payload["feedback_md"]
    assert result.analysis_json["criteria_results"][0]["score"] == 8


def test_parser_logs_when_raw_payload_not_json(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """If the LM answer is not JSON, log a parse failure with a redacted sample."""
    _install_fake_dspy(monkeypatch)
    from importlib import import_module

    mod = import_module("backend.learning.adapters.dspy.feedback_program")

    monkeypatch.setattr(mod, "_run_model", lambda **_: "### not json", raising=False)  # type: ignore[attr-defined]
    monkeypatch.setattr(mod, "_run_feedback_model", lambda **_: "**Stub Feedback**", raising=False)  # type: ignore[attr-defined]

    caplog.set_level("INFO")
    result = mod.analyze_feedback(  # type: ignore[attr-defined]
        text_md="# Text", criteria=["Inhalt"]
    )

    assert result.parse_status == "analysis_fallback"
    assert any("learning.feedback.dspy_parse_failed" in record.getMessage() for record in caplog.records), \
        "Expected parse failure log entry"


def test_parser_handles_json_code_fences(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLMs often wrap JSON responses in ```json fences; parser should unwrap them."""
    _install_fake_dspy(monkeypatch)
    from importlib import import_module

    mod = import_module("backend.learning.adapters.dspy.feedback_program")

    payload = {
        "schema": "criteria.v2",
        "score": 4,
        "criteria_results": [
            {"criterion": "Inhalt", "max_score": 10, "score": 9, "explanation_md": "stark"},
            {"criterion": "Struktur", "max_score": 10, "score": 5, "explanation_md": "geht"},
        ],
    }
    fenced = f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```"

    monkeypatch.setattr(mod, "_run_model", lambda **_: fenced, raising=False)  # type: ignore[attr-defined]
    monkeypatch.setattr(mod, "_run_feedback_model", lambda **_: "**LLM Feedback**", raising=False)  # type: ignore[attr-defined]

    result = mod.analyze_feedback(  # type: ignore[attr-defined]
        text_md="# Text", criteria=["Inhalt", "Struktur"]
    )
    assert result.parse_status == "parsed"
    scores = [item["score"] for item in result.analysis_json["criteria_results"]]
    assert scores == [9, 5]


def test_parser_extracts_json_from_wrapped_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """If a response contains prose plus a fenced JSON block, parser should use the block."""
    _install_fake_dspy(monkeypatch)
    from importlib import import_module

    mod = import_module("backend.learning.adapters.dspy.feedback_program")

    payload = {
        "criteria_results": [
            {"criterion": "Inhalt", "max_score": 10, "score": 7, "explanation_md": "ok"},
        ],
    }
    wrapped = "Hier ist die Analyse:\n```JSON\n" + json.dumps(payload) + "\n```\nDanke!"

    monkeypatch.setattr(mod, "_run_model", lambda **_: wrapped, raising=False)  # type: ignore[attr-defined]
    monkeypatch.setattr(mod, "_run_feedback_model", lambda **_: "**LLM Feedback**", raising=False)  # type: ignore[attr-defined]

    result = mod.analyze_feedback(  # type: ignore[attr-defined]
        text_md="# Text", criteria=["Inhalt"]
    )
    assert result.parse_status == "parsed"
    assert result.analysis_json["criteria_results"][0]["score"] == 7


def test_two_phase_pipeline_uses_analysis_and_feedback_programs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DSPy path should call analysis first and pass normalized JSON to feedback synthesis."""
    _install_fake_dspy(monkeypatch)
    from importlib import import_module

    mod = import_module("backend.learning.adapters.dspy.feedback_program")

    calls: dict[str, bool] = {"analysis": False, "feedback": False}

    def fake_analysis(*, text_md: str, criteria: list[str]) -> str:
        calls["analysis"] = True
        assert "# Text" in text_md
        return json.dumps(
            {
                "schema": "criteria.v2",
                "score": 4,
                "criteria_results": [
                    {
                        "criterion": criteria[0],
                        "max_score": 10,
                        "score": 8,
                        "explanation_md": "OK",
                    }
                ],
            }
        )

    def fake_feedback(*, text_md: str, criteria: list[str], analysis_json: dict) -> str:
        calls["feedback"] = True
        assert analysis_json["criteria_results"][0]["score"] == 8
        assert criteria == ["Inhalt"]
        return "**LLM Feedback**\n\n- Inhalt: 8/10"

    monkeypatch.setattr(mod, "_run_analysis_model", fake_analysis, raising=False)  # type: ignore[attr-defined]
    monkeypatch.setattr(mod, "_run_feedback_model", fake_feedback, raising=False)  # type: ignore[attr-defined]
    monkeypatch.setattr(
        mod,
        "_run_model",
        lambda **_: (_ for _ in ()).throw(AssertionError("legacy single-phase runner must not execute")),
        raising=False,
    )  # type: ignore[attr-defined]

    result = mod.analyze_feedback(  # type: ignore[attr-defined]
        text_md="# Text", criteria=["Inhalt"]
    )

    assert calls["analysis"] is True, "analysis stage should run first"
    assert calls["feedback"] is True, "feedback stage should run second"
    assert result.feedback_md.startswith("**LLM Feedback**")
    assert result.analysis_json["criteria_results"][0]["score"] == 8


def test_two_phase_pipeline_falls_back_when_analysis_invalid(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """If analysis JSON is invalid, fall back to defaults but still run feedback synthesis."""
    _install_fake_dspy(monkeypatch)
    from importlib import import_module

    mod = import_module("backend.learning.adapters.dspy.feedback_program")

    def fake_analysis(*, text_md: str, criteria: list[str]) -> str:
        return "not json"

    captured: dict[str, list[dict]] = {}

    def fake_feedback(*, text_md: str, criteria: list[str], analysis_json: dict) -> str:
        captured["analysis_json"] = analysis_json["criteria_results"]
        return "**Fallback Feedback**"

    monkeypatch.setattr(mod, "_run_analysis_model", fake_analysis, raising=False)  # type: ignore[attr-defined]
    monkeypatch.setattr(mod, "_run_feedback_model", fake_feedback, raising=False)  # type: ignore[attr-defined]
    monkeypatch.setattr(
        mod,
        "_run_model",
        lambda **_: (_ for _ in ()).throw(AssertionError("legacy single-phase runner must not execute")),
        raising=False,
    )  # type: ignore[attr-defined]

    caplog.set_level("WARNING")
    result = mod.analyze_feedback(  # type: ignore[attr-defined]
        text_md="# Text", criteria=["Inhalt", "Struktur"]
    )

    assert any("learning.feedback.dspy_parse_failed" in record.getMessage() for record in caplog.records)
    assert result.parse_status == "analysis_fallback"
    assert "analysis_json" in captured, "feedback synthesis must run even on analysis fallback"
    assert captured["analysis_json"][0]["criterion"] == "Inhalt"
    assert result.feedback_md == "**Fallback Feedback**"
    assert result.analysis_json["criteria_results"][0]["criterion"] == "Inhalt"
