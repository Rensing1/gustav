from __future__ import annotations

import json

from backend.learning.adapters.dspy import feedback_program as fp


def test_feedback_prompt_omits_full_analysis_json_when_huge():
    # Arrange a very large analysis payload
    huge_text = "X" * 200_000
    analysis = {
        "schema": "criteria.v2",
        "score": 3,
        "criteria_results": [
            {"criterion": "K1", "max_score": 10, "score": 5, "explanation_md": "ok"},
            {"criterion": "K2", "max_score": 10, "score": 7, "explanation_md": huge_text},
        ],
    }

    # Act
    prompt = fp._build_feedback_prompt(  # type: ignore[attr-defined]
        text_md=huge_text,
        criteria=["K1", "K2"],
        analysis_json=analysis,
        teacher_instructions_md=huge_text,
    )

    # Assert: prompt is bounded and does not embed the full JSON blob
    assert len(prompt) < 30_000
    assert "Analyse-JSON (vollständig):" not in prompt
    # Critical content remains present in summary lines
    assert "- K1: 5/10" in prompt and "- K2: 7/10" in prompt


def test_analysis_prompt_is_bounded_with_long_sections():
    huge = "Y" * 300_000
    prompt = fp._build_analysis_prompt(  # type: ignore[attr-defined]
        text_md=huge,
        criteria=["A", "B"],
        teacher_instructions_md=huge,
        solution_hints_md=huge,
    )
    assert len(prompt) < 30_000
    # Contains key structural markers
    assert "Kriterien (Reihenfolge beibehalten)" in prompt
    assert "Schülertext (wörtlich):" in prompt
