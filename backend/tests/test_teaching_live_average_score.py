"""
Teaching Live — Average score helper (unit tests).
"""
from __future__ import annotations

import importlib

import pytest

teaching = importlib.import_module("backend.web.routes.teaching")


def test_compute_average_score_from_analysis_normalises_max_scores():
    analysis = {
        "schema": "criteria.v2",
        "criteria_results": [
            {"criterion": "K1", "score": 4, "max_score": 5},
            {"criterion": "K2", "score": 8, "max_score": 10},
        ],
    }
    score = teaching.compute_average_score_from_analysis(analysis)
    assert score == pytest.approx(8.0)


def test_compute_average_score_from_analysis_ignores_invalid_scores():
    analysis = {
        "schema": "criteria.v2",
        "criteria_results": [
            {"criterion": "Valid", "score": 5},
            {"criterion": "Invalid", "score": "n/a"},
        ],
    }
    score = teaching.compute_average_score_from_analysis(analysis)
    assert score == pytest.approx(5.0)


def test_compute_average_score_from_analysis_returns_none_without_scores():
    analysis = {
        "schema": "criteria.v2",
        "criteria_results": [
            {"criterion": "NoScore"},
            {"criterion": "BadScore", "score": "x"},
        ],
    }
    assert teaching.compute_average_score_from_analysis(analysis) is None
