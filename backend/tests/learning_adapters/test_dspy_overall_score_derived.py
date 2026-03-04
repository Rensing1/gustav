"""Derive overall score from lean criterion-indexed DSPy analysis output."""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import pytest


def _install_fake_dspy(monkeypatch: pytest.MonkeyPatch, *, criteria_results: list[dict]) -> None:
    class _Predict:  # minimal callable compatible with dspy.Predict(Signature)
        def __init__(self, _signature):  # noqa: ANN001
            self._signature = _signature

        def __call__(self, **_kwargs):  # noqa: ANN003
            # Important: no `overall_score` attribute.
            return SimpleNamespace(criteria_results=criteria_results)

    def _image(*, url: str):  # noqa: ANN001
        return SimpleNamespace(url=url)

    fake_dspy = SimpleNamespace(__version__="0.0-test", Predict=_Predict, Image=_image)
    monkeypatch.setitem(sys.modules, "dspy", fake_dspy)


def _reload_programs() -> object:
    # Ensure signatures/programs are re-imported under the current fake dspy.
    for mod in [
        "backend.learning.adapters.dspy.signatures",
        "backend.learning.adapters.dspy.programs",
    ]:
        sys.modules.pop(mod, None)
    return importlib.import_module("backend.learning.adapters.dspy.programs")


def test_run_structured_analysis_derives_score_from_criteria_results(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_dspy(
        monkeypatch,
        criteria_results=[
            {"criterion_idx": 1, "score": 10, "explanation_md": "OK B"},
            {"criterion_idx": 0, "score": 0, "explanation_md": "OK A"},
        ],
    )
    programs = _reload_programs()

    analysis = programs.run_structured_analysis(  # type: ignore[attr-defined]
        text_md="Text",
        criteria=["A", "B"],
        teacher_instructions_md="Instr",
        teacher_context_md="Ctx",
    )
    payload = analysis.to_dict()
    assert payload["schema"] == "criteria.v2"
    assert payload["criteria_results"] == [
        {"criterion": "A", "max_score": 10, "score": 0, "explanation_md": "OK A"},
        {"criterion": "B", "max_score": 10, "score": 10, "explanation_md": "OK B"},
    ]
    # Average 10 and 0 -> 5/10 -> derived overall score 3/5 (rounded).
    assert payload["score"] == 3


def test_run_structured_visual_analysis_derives_score_from_criteria_results(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_dspy(
        monkeypatch,
        criteria_results=[
            {"criterion_idx": 0, "score": 10, "explanation_md": "OK A"},
            {"criterion_idx": 1, "score": 8, "explanation_md": "OK B"},
        ],
    )
    programs = _reload_programs()

    analysis = programs.run_structured_visual_analysis(  # type: ignore[attr-defined]
        image_data_uri="data:image/png;base64,AAAA",
        criteria=["A", "B"],
        teacher_instructions_md="Instr",
        teacher_context_md="Ctx",
    )
    payload = analysis.to_dict()
    assert payload["schema"] == "criteria.v2"
    assert payload["criteria_results"] == [
        {"criterion": "A", "max_score": 10, "score": 10, "explanation_md": "OK A"},
        {"criterion": "B", "max_score": 10, "score": 8, "explanation_md": "OK B"},
    ]
    # Average normalized score: (10 + 8) / 2 = 9 -> 9/10 -> derived overall 5/5 (rounded).
    assert payload["score"] == 5


def test_run_structured_analysis_raises_when_criterion_idx_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_dspy(
        monkeypatch,
        criteria_results=[
            {"score": 6, "explanation_md": "OK"},
        ],
    )
    programs = _reload_programs()

    with pytest.raises(RuntimeError, match="invalid_criterion_idx"):
        _ = programs.run_structured_analysis(  # type: ignore[attr-defined]
            text_md="Text",
            criteria=["A"],
            teacher_instructions_md="Instr",
            teacher_context_md="Ctx",
        )


def test_run_structured_analysis_raises_when_criterion_idx_out_of_range(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_dspy(
        monkeypatch,
        criteria_results=[
            {"criterion_idx": 3, "score": 6, "explanation_md": "OK"},
        ],
    )
    programs = _reload_programs()

    with pytest.raises(RuntimeError, match="invalid_criterion_idx"):
        _ = programs.run_structured_analysis(  # type: ignore[attr-defined]
            text_md="Text",
            criteria=["A", "B"],
            teacher_instructions_md="Instr",
            teacher_context_md="Ctx",
        )


def test_run_structured_analysis_raises_when_criterion_idx_duplicated(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_dspy(
        monkeypatch,
        criteria_results=[
            {"criterion_idx": 0, "score": 4, "explanation_md": "OK A1"},
            {"criterion_idx": 0, "score": 7, "explanation_md": "OK A2"},
        ],
    )
    programs = _reload_programs()

    with pytest.raises(RuntimeError, match="invalid_criterion_idx"):
        _ = programs.run_structured_analysis(  # type: ignore[attr-defined]
            text_md="Text",
            criteria=["A", "B"],
            teacher_instructions_md="Instr",
            teacher_context_md="Ctx",
        )
