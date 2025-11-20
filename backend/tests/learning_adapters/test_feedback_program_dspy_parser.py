"""
Parser/normalization tests for the DSPy feedback program (criteria.v2).

Scope:
    These tests exercise the pure parsing helpers used by the DSPy-only
    pipeline (`_parse_to_v2`, `_unwrap_code_block`). They no longer depend
    on legacy LM runners and instead focus on:
      - accepting minor field-name variations,
      - clamping scores into valid ranges,
      - filling missing criteria deterministically,
      - handling malformed JSON and fenced code blocks.
"""

from __future__ import annotations

import json

import pytest


def test_parser_does_not_duplicate_criterion_in_explanation() -> None:
    """Explanations should stay concise and not repeat the criterion name."""
    from importlib import import_module

    mod = import_module("backend.learning.adapters.dspy.feedback_program")

    raw = json.dumps(
        {
            "criteria_results": [
                {"criterion": "Inhalt", "max_score": 10, "score": 0, "explanation_md": "Kein Beleg gefunden."},
                {"criterion": "Struktur", "max_score": 10, "score": 5},
            ]
        },
        ensure_ascii=False,
    )

    analysis, _ = mod._parse_to_v2(raw, criteria=["Inhalt", "Struktur"])  # type: ignore[attr-defined]
    assert analysis is not None
    explanations = {item["criterion"]: item["explanation_md"] for item in analysis["criteria_results"]}

    assert explanations["Inhalt"] == "Kein Beleg gefunden."
    assert "Bezug:" not in explanations["Inhalt"]
    assert "Bezug" not in explanations["Struktur"]
    assert explanations["Struktur"] == "Kein Beleg im Schülertext gefunden."


def test_parser_accepts_variants_and_clamps() -> None:
    from importlib import import_module

    mod = import_module("backend.learning.adapters.dspy.feedback_program")

    raw = (
        "{\n"
        '  "schema": "criteria.v2",\n'
        '  "score": 9,\n'
        '  "criteria": [\n'
        '    {"name": "Inhalt", "max": 10, "score": 11, "explanation": "gut"},\n'
        '    {"name": "Struktur", "max": 8, "score": -2, "explanation_md": "verbesserbar"}\n'
        "  ]\n"
        "}\n"
    )

    analysis, embedded_feedback = mod._parse_to_v2(raw, criteria=["Inhalt", "Struktur"])  # type: ignore[attr-defined]
    assert embedded_feedback is None
    assert analysis is not None
    assert analysis.get("schema") == "criteria.v2"
    assert analysis.get("score") == 5  # clamped overall score

    items = analysis.get("criteria_results")
    assert len(items) == 2
    a, b = items[0], items[1]
    assert a["criterion"] == "Inhalt" and a["max_score"] == 10 and a["score"] == 10
    assert b["criterion"] == "Struktur" and b["max_score"] == 8 and b["score"] == 0
    assert a["explanation_md"] == "gut"
    assert b["explanation_md"] == "verbesserbar"


def test_parser_fills_missing_criteria_and_defaults_on_malformed() -> None:
    from importlib import import_module

    mod = import_module("backend.learning.adapters.dspy.feedback_program")

    raw_one = (
        "{\n"
        '  "criteria_results": [ { "criterion": "Inhalt", "max_score": 10, "score": 4, "explanation_md": "ok" } ]\n'
        "}\n"
    )
    analysis, _ = mod._parse_to_v2(raw_one, criteria=["Inhalt", "Struktur"])  # type: ignore[attr-defined]
    assert analysis is not None
    items = analysis.get("criteria_results")
    assert len(items) == 2
    names = {it["criterion"] for it in items}
    assert names == {"Inhalt", "Struktur"}
    filled = {it["criterion"]: it for it in items}
    assert filled["Struktur"]["score"] == 0

    malformed = "not json at all"
    analysis2, _ = mod._parse_to_v2(malformed, criteria=["Inhalt", "Struktur"])  # type: ignore[attr-defined]
    assert analysis2 is None


def test_parser_passes_through_embedded_feedback() -> None:
    """If the model embeds `feedback_md` in the JSON, expose it as secondary output."""
    from importlib import import_module

    mod = import_module("backend.learning.adapters.dspy.feedback_program")

    payload = {
        "schema": "criteria.v2",
        "score": 4,
        "criteria_results": [
            {"criterion": "Inhalt", "max_score": 10, "score": 8, "explanation_md": "ok"},
        ],
        "feedback_md": "**Lob**\n\n- Gute Argumente.",
    }
    raw = json.dumps(payload, ensure_ascii=False)

    analysis, embedded_feedback = mod._parse_to_v2(raw, criteria=["Inhalt"])  # type: ignore[attr-defined]
    assert analysis is not None
    assert analysis["criteria_results"][0]["score"] == 8
    assert embedded_feedback == payload["feedback_md"]


def test_parser_logs_when_raw_payload_not_json(caplog: pytest.LogCaptureFixture) -> None:
    """If the LM answer is not JSON, log a parse failure with a redacted sample."""
    from importlib import import_module

    mod = import_module("backend.learning.adapters.dspy.feedback_program")

    caplog.set_level("INFO")
    analysis, _ = mod._parse_to_v2("### not json", criteria=["Inhalt"])  # type: ignore[attr-defined]

    assert analysis is None
    assert any("learning.feedback.dspy_parse_failed" in record.getMessage() for record in caplog.records), (
        "Expected parse failure log entry"
    )


def test_parser_handles_json_code_fences() -> None:
    """LLMs often wrap JSON responses in ```json fences; parser should unwrap them."""
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

    analysis, _ = mod._parse_to_v2(fenced, criteria=["Inhalt", "Struktur"])  # type: ignore[attr-defined]
    assert analysis is not None
    scores = [item["score"] for item in analysis["criteria_results"]]
    assert scores == [9, 5]


def test_parser_extracts_json_from_wrapped_text() -> None:
    """If a response contains prose plus a fenced JSON block, parser should use the block."""
    from importlib import import_module

    mod = import_module("backend.learning.adapters.dspy.feedback_program")

    payload = {
        "criteria_results": [
            {"criterion": "Inhalt", "max_score": 10, "score": 7, "explanation_md": "ok"},
        ],
    }
    wrapped = "Hier ist die Analyse:\n```JSON\n" + json.dumps(payload) + "\n```\nDanke!"

    analysis, _ = mod._parse_to_v2(wrapped, criteria=["Inhalt"])  # type: ignore[attr-defined]
    assert analysis is not None
    assert analysis["criteria_results"][0]["score"] == 7
