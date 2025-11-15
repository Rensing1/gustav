"""
Tests for aligning DSPy structured outputs to expected criteria names by order.

Intent:
    If the model returns criteria_results with different names but in the
    correct order and count, we relabel them to the expected input names,
    preserving the scores and explanations. This avoids zeroed "stub" rows
    caused by strict name matching.
"""

from __future__ import annotations

import json

from backend.learning.adapters.dspy.feedback_program import _parse_to_v2


def test_parse_to_v2_aligns_items_by_order() -> None:
    # Model output with different names but correct order and scores
    raw = json.dumps(
        {
            "schema": "criteria.v2",
            "score": 4,
            "criteria_results": [
                {"criterion": "Content", "max_score": 10, "score": 8, "explanation_md": "OK"},
                {"criterion": "Structure", "max_score": 10, "score": 6, "explanation_md": "OK"},
            ],
        }
    )
    expected = ["Inhalt", "Struktur"]

    analysis, _ = _parse_to_v2(raw, criteria=expected)
    assert analysis is not None
    items = analysis["criteria_results"]
    assert [i["criterion"] for i in items] == expected
    assert [i["score"] for i in items] == [8, 6]

