"""
Teaching Live — Average score helper (unit tests).
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

teaching = importlib.import_module("backend.web.routes.teaching")
row_mappers = importlib.import_module("backend.teaching.repo_row_mappers")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEACHING_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching.py"


def test_average_score_helper_is_owned_by_repo_row_mappers():
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")

    assert "def compute_average_score_from_analysis(" not in teaching_source
    assert teaching.compute_average_score_from_analysis is row_mappers.compute_average_score_from_analysis


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
