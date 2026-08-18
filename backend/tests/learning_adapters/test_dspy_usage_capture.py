from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from backend.learning.adapters.dspy.usage import capture_dspy_usage


def test_capture_dspy_usage_maps_mistral_compatible_token_shape(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class _Tracker:
        usage_data = {
            "openai/mistral-small-latest": [
                {"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17},
            ]
        }

    @contextmanager
    def _track_usage():  # type: ignore[no-untyped-def]
        yield _Tracker()

    monkeypatch.setitem(__import__("sys").modules, "dspy", SimpleNamespace(track_usage=_track_usage))

    result, events = capture_dspy_usage(
        lambda: "ok",
        model="fallback-model",
        stage="feedback",
        modality="text",
        call_kind="primary",
    )

    assert result == "ok"
    assert len(events) == 1
    event = events[0]
    assert event.model == "openai/mistral-small-latest"
    assert event.input_tokens == 12
    assert event.output_tokens == 5
    assert event.total_tokens == 17
    assert event.usage_known is True


def test_capture_dspy_usage_keeps_total_only_usage_known(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class _Tracker:
        usage_data = {"openai/provider-model": [{"total_tokens": 21}]}

    @contextmanager
    def _track_usage():  # type: ignore[no-untyped-def]
        yield _Tracker()

    monkeypatch.setitem(__import__("sys").modules, "dspy", SimpleNamespace(track_usage=_track_usage))

    _result, events = capture_dspy_usage(
        lambda: "ok",
        model="fallback-model",
        stage="analysis",
        modality="visual",
        call_kind="repair",
    )

    assert len(events) == 1
    assert events[0].input_tokens is None
    assert events[0].output_tokens is None
    assert events[0].total_tokens == 21
    assert events[0].usage_known is True


def test_capture_dspy_usage_records_unknown_event_when_provider_omits_usage(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class _Tracker:
        usage_data = {"openai/provider-model": [{}]}

    @contextmanager
    def _track_usage():  # type: ignore[no-untyped-def]
        yield _Tracker()

    monkeypatch.setitem(__import__("sys").modules, "dspy", SimpleNamespace(track_usage=_track_usage))

    _result, events = capture_dspy_usage(
        lambda: "ok",
        model="fallback-model",
        stage="feedback",
        modality="text",
        call_kind="primary",
    )

    assert len(events) == 1
    assert events[0].model == "openai/provider-model"
    assert events[0].usage_known is False
    assert events[0].input_tokens is None
    assert events[0].output_tokens is None
    assert events[0].total_tokens is None
    assert events[0].unknown_reason == "missing_provider_usage"


def test_capture_dspy_usage_attaches_events_to_parse_error(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class _Tracker:
        usage_data = {"openai/provider-model": [{"prompt_tokens": 9, "completion_tokens": 4, "total_tokens": 13}]}

    @contextmanager
    def _track_usage():  # type: ignore[no-untyped-def]
        yield _Tracker()

    monkeypatch.setitem(__import__("sys").modules, "dspy", SimpleNamespace(track_usage=_track_usage))

    with pytest.raises(RuntimeError) as raised:
        capture_dspy_usage(
            lambda: (_ for _ in ()).throw(RuntimeError("invalid_analysis_json")),
            model="fallback-model",
            stage="analysis",
            modality="text",
            call_kind="primary",
        )

    events = getattr(raised.value, "usage_events", [])
    assert len(events) == 1
    assert events[0].input_tokens == 9
    assert events[0].output_tokens == 4


def test_empty_feedback_validation_error_keeps_captured_usage_events(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class _Tracker:
        usage_data = {"openai/provider-model": [{"prompt_tokens": 15, "completion_tokens": 3, "total_tokens": 18}]}

    @contextmanager
    def _track_usage():  # type: ignore[no-untyped-def]
        yield _Tracker()

    monkeypatch.setitem(
        __import__("sys").modules,
        "dspy",
        SimpleNamespace(__version__="test", track_usage=_track_usage, context=lambda **_kwargs: _track_usage()),
    )

    from backend.learning.adapters.dspy import feedback_program

    monkeypatch.setattr(feedback_program.dspy_programs, "run_feedback_no_criteria", lambda **_kwargs: "   ")

    with pytest.raises(RuntimeError) as raised:
        feedback_program.analyze_feedback(text_md="Antwort", criteria=[])

    assert str(raised.value) == "empty_feedback_md"
    events = getattr(raised.value, "usage_events", [])
    assert len(events) == 1
    assert events[0].input_tokens == 15
    assert events[0].output_tokens == 3
