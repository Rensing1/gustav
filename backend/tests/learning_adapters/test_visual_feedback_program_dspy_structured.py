"""
Structured DSPy pipeline tests for Visual tasks (image → analysis → feedback).

Intent:
    Encode the contract for the Visual DSPy program:
      - It requires DSPy to be importable.
      - It calls the structured runners (analysis + feedback) that accept a
        visual input (data-URI image) instead of plain text.
      - It returns a `criteria.v2`-shaped analysis_json plus prose feedback.

Notes:
    These tests stay deterministic by monkeypatching the structured runners
    at `backend.learning.adapters.dspy.programs` (no real LM calls).
"""

from __future__ import annotations

import builtins
import importlib
import logging
import sys
from types import SimpleNamespace

import pytest


def _install_fake_dspy(monkeypatch: pytest.MonkeyPatch) -> None:
    # For this unit test we only need "import dspy" to succeed.
    monkeypatch.setitem(sys.modules, "dspy", SimpleNamespace(__version__="3.0.3"))


def _hide_dspy_import(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "dspy":
            raise ImportError("dspy intentionally hidden for test")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)


def test_visual_feedback_program_raises_when_dspy_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    if "dspy" in sys.modules:
        monkeypatch.delitem(sys.modules, "dspy", raising=False)
    _hide_dspy_import(monkeypatch)

    mod = importlib.import_module("backend.learning.adapters.dspy.visual_feedback_program")
    with pytest.raises(ImportError):
        _ = mod.analyze_visual_feedback(  # type: ignore[attr-defined]
            image_data_uri="data:image/png;base64,AA==",
            criteria=["K1"],
            teacher_instructions_md="Aufgabe",
            teacher_context_md=None,
        )


def test_visual_feedback_program_structured_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_dspy(monkeypatch)

    programs = importlib.import_module("backend.learning.adapters.dspy.programs")

    def fake_run_structured_visual_analysis(
        *,
        image_data_uri: str,
        criteria: list[str],
        teacher_instructions_md=None,
        teacher_context_md=None,
    ):
        assert image_data_uri.startswith("data:image/"), "visual pipeline must receive an image data URI"
        return {
            "schema": "criteria.v2",
            # Out-of-range overall to ensure clamping.
            "score": 9,
            "criteria_results": [
                {"criterion": criteria[0], "max_score": 10, "score": 11, "explanation_md": "ok"},
                {"criterion": criteria[1], "max_score": 10, "score": -1, "explanation_md": "gut"},
            ],
        }

    def fake_run_structured_visual_feedback(
        *,
        image_data_uri: str,
        criteria: list[str],
        analysis_json: dict,
        teacher_instructions_md=None,
        teacher_context_md=None,
    ):
        assert image_data_uri.startswith("data:image/"), "visual feedback must receive an image data URI"
        assert analysis_json.get("schema") == "criteria.v2"
        return (
            "**Das ist Ihnen gut gelungen:** Ihre Lösung ist gut nachvollziehbar.\n\n"
            "**Das können Sie noch besser:** Begründen Sie einzelne Schritte noch etwas genauer."
        )

    monkeypatch.setattr(programs, "run_structured_visual_analysis", fake_run_structured_visual_analysis, raising=False)
    monkeypatch.setattr(programs, "run_structured_visual_feedback", fake_run_structured_visual_feedback, raising=False)

    mod = importlib.import_module("backend.learning.adapters.dspy.visual_feedback_program")
    result = mod.analyze_visual_feedback(  # type: ignore[attr-defined]
        image_data_uri="data:image/png;base64,AA==",
        criteria=["Inhalt", "Struktur"],
        teacher_instructions_md="Aufgabe",
        teacher_context_md="Hinweis",
    )

    assert result.parse_status == "parsed_structured"
    assert result.analysis_json.get("schema") == "criteria.v2"
    items = result.analysis_json.get("criteria_results")
    assert isinstance(items, list) and len(items) == 2
    assert items[0]["criterion"] == "Inhalt" and items[1]["criterion"] == "Struktur"
    assert "**Das ist Ihnen gut gelungen:**" in result.feedback_md
    assert "**Das können Sie noch besser:**" in result.feedback_md


def test_visual_feedback_program_empty_criteria_uses_synthesis_context(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: list[dict] = []

    class _FakeJsonAdapter:
        pass

    class _FakeDspy:
        __version__ = "3.0.3"
        JSONAdapter = _FakeJsonAdapter

        @staticmethod
        def context(**kwargs):  # type: ignore[no-untyped-def]
            class _Ctx:
                def __enter__(self_inner):
                    observed.append(dict(kwargs))
                    return None

                def __exit__(self_inner, exc_type, exc, tb):
                    return False

            return _Ctx()

    monkeypatch.setitem(sys.modules, "dspy", _FakeDspy())
    programs = importlib.import_module("backend.learning.adapters.dspy.programs")

    monkeypatch.setattr(
        programs,
        "run_visual_feedback_no_criteria",
        lambda **_kwargs: (
            "**Das ist Ihnen gut gelungen:** Ihre Lösung ist gut nachvollziehbar.\n\n"
            "**Das können Sie noch besser:** Begründen Sie einzelne Schritte noch etwas genauer."
        ),
        raising=False,
    )

    mod = importlib.import_module("backend.learning.adapters.dspy.visual_feedback_program")
    result = mod.analyze_visual_feedback(  # type: ignore[attr-defined]
        image_data_uri="data:image/png;base64,AA==",
        criteria=[],
        synthesis_lm=object(),
    )

    assert result.analysis_json == {}
    assert result.parse_status == "skipped"
    assert len(observed) == 1
    assert observed[0]["lm"] is not None


def test_visual_feedback_program_accepts_teacher_requested_free_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_dspy(monkeypatch)
    programs = importlib.import_module("backend.learning.adapters.dspy.programs")
    monkeypatch.setattr(
        programs,
        "run_structured_visual_analysis",
        lambda **_kwargs: {
            "schema": "criteria.v2",
            "score": 4,
            "criteria_results": [
                {"criterion": "Darstellung", "max_score": 10, "score": 8, "explanation_md": "Sichtbar."},
            ],
        },
        raising=False,
    )
    monkeypatch.setattr(
        programs,
        "run_structured_visual_feedback",
        lambda **_kwargs: "Ihre Darstellung ist gut lesbar; kennzeichnen Sie noch die entscheidende Verbindung.",
        raising=False,
    )

    mod = importlib.import_module("backend.learning.adapters.dspy.visual_feedback_program")
    result = mod.analyze_visual_feedback(  # type: ignore[attr-defined]
        image_data_uri="data:image/png;base64,AA==",
        criteria=["Darstellung"],
        teacher_context_md="Antworten Sie in einem Satz ohne Überschriften.",
    )

    assert result.feedback_md.startswith("Ihre Darstellung")


def test_visual_feedback_without_criteria_accepts_teacher_requested_free_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_dspy(monkeypatch)
    programs = importlib.import_module("backend.learning.adapters.dspy.programs")
    monkeypatch.setattr(
        programs,
        "run_visual_feedback_no_criteria",
        lambda **_kwargs: "Sie haben die zentralen Elemente sichtbar angeordnet.",
        raising=False,
    )

    mod = importlib.import_module("backend.learning.adapters.dspy.visual_feedback_program")
    result = mod.analyze_visual_feedback(  # type: ignore[attr-defined]
        image_data_uri="data:image/png;base64,AA==",
        criteria=[],
    )

    assert result.feedback_md == "Sie haben die zentralen Elemente sichtbar angeordnet."


def test_visual_feedback_program_retries_analysis_once_after_invalid_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_dspy(monkeypatch)
    programs = importlib.import_module("backend.learning.adapters.dspy.programs")
    calls = {"analysis": 0, "repair": 0}

    def fake_run_structured_visual_analysis(**_kwargs):
        calls["analysis"] += 1
        raise RuntimeError("invalid_analysis_json")

    def fake_run_structured_visual_analysis_repair(*, repair_reason: str, **_kwargs):
        calls["repair"] += 1
        assert repair_reason == "invalid_analysis_json"
        return {
            "schema": "criteria.v2",
            "score": 4,
            "criteria_results": [
                {"criterion": "Inhalt", "max_score": 10, "score": 7, "explanation_md": "ok"},
                {"criterion": "Struktur", "max_score": 10, "score": 8, "explanation_md": "gut"},
            ],
        }

    def fake_run_structured_visual_feedback(*, analysis_json: dict, **_kwargs):
        assert analysis_json.get("schema") == "criteria.v2"
        return (
            "**Das ist Ihnen gut gelungen:** Ihre Lösung ist gut nachvollziehbar.\n\n"
            "**Das können Sie noch besser:** Begründen Sie einzelne Schritte noch etwas genauer."
        )

    monkeypatch.setattr(programs, "run_structured_visual_analysis", fake_run_structured_visual_analysis, raising=False)
    monkeypatch.setattr(
        programs,
        "run_structured_visual_analysis_repair",
        fake_run_structured_visual_analysis_repair,
        raising=False,
    )
    monkeypatch.setattr(programs, "run_structured_visual_feedback", fake_run_structured_visual_feedback, raising=False)

    mod = importlib.import_module("backend.learning.adapters.dspy.visual_feedback_program")
    result = mod.analyze_visual_feedback(  # type: ignore[attr-defined]
        image_data_uri="data:image/png;base64,AA==",
        criteria=["Inhalt", "Struktur"],
        teacher_instructions_md="Aufgabe",
        teacher_context_md="Hinweis",
    )

    assert calls == {"analysis": 1, "repair": 1}
    assert result.parse_status == "repaired_structured"


def test_visual_feedback_program_logs_stage_metadata(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _install_fake_dspy(monkeypatch)
    programs = importlib.import_module("backend.learning.adapters.dspy.programs")
    observability = importlib.import_module("backend.learning.adapters.dspy.json_observability")

    monkeypatch.setattr(
        programs,
        "run_structured_visual_analysis",
        lambda **_kwargs: {
            "schema": "criteria.v2",
            "score": 4,
            "criteria_results": [
                {"criterion": "Inhalt", "max_score": 10, "score": 7, "explanation_md": "ok"},
            ],
        },
        raising=False,
    )
    monkeypatch.setattr(
        programs,
        "run_structured_visual_feedback",
        lambda **_kwargs: (
            "**Das ist Ihnen gut gelungen:** Ihre Lösung ist gut nachvollziehbar.\n\n"
            "**Das können Sie noch besser:** Begründen Sie einzelne Schritte noch etwas genauer."
        ),
        raising=False,
    )

    metadata = iter(
        [
            {
                "stage": "visual_analysis",
                "model": "openai/mistral-small-4",
                "provider": "openai",
                "response_format_mode": "json_schema",
                "reasoning_effort": "none",
            },
            {
                "stage": "visual_synthesis",
                "model": "openai/mistral-small-4",
                "provider": "openai",
                "response_format_mode": "json_object_fallback",
                "reasoning_effort": "none",
            },
        ]
    )
    monkeypatch.setattr(observability, "pop_last_call_metadata", lambda: next(metadata, None))
    monkeypatch.setattr(observability, "build_json_adapter", lambda **_kwargs: object())

    mod = importlib.import_module("backend.learning.adapters.dspy.visual_feedback_program")
    caplog.set_level(logging.INFO)
    mod.analyze_visual_feedback(  # type: ignore[attr-defined]
        image_data_uri="data:image/png;base64,AA==",
        criteria=["Inhalt"],
    )

    messages = [record.getMessage() for record in caplog.records]
    assert any("learning.feedback.dspy_stage_completed" in message for message in messages)
    assert any("learning.feedback.dspy_response_format_fallback" in message for message in messages)
