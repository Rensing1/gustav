"""Deterministic completion rules for native practice attempts."""

from __future__ import annotations

import pytest

from backend.learning.practice.completion import fulfillment_from_analysis


def test_fulfillment_uses_weighted_criterion_points() -> None:
    analysis = {
        "criteria_results": [
            {"criterion": "A", "score": 8, "max_score": 10},
            {"criterion": "B", "score": 1, "max_score": 2},
        ]
    }
    assert fulfillment_from_analysis(analysis, ["A", "B"]) == pytest.approx(0.75)


@pytest.mark.parametrize(
    "analysis,criteria",
    [
        ({"criteria_results": []}, ["A"]),
        ({"criteria_results": [{"criterion": "A", "score": 1, "max_score": 0}]}, ["A"]),
        ({"criteria_results": [{"criterion": "A", "score": 11, "max_score": 10}]}, ["A"]),
        ({"criteria_results": [{"criterion": "B", "score": 5, "max_score": 10}]}, ["A"]),
    ],
)
def test_fulfillment_rejects_incomplete_or_untrusted_analysis(analysis: dict, criteria: list[str]) -> None:
    with pytest.raises(ValueError, match="invalid_practice_analysis"):
        fulfillment_from_analysis(analysis, criteria)
