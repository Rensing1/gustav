"""Token-accounting contract for the final dialog assessment."""

from __future__ import annotations

import pytest

from backend.learning.adapters import local_feedback
from backend.learning.adapters.dspy import dialog_assessment_program
from backend.learning.adapters.ports import FeedbackResult, TokenUsageEvent
from backend.learning.adapters.ports import FeedbackTransientError


def test_dialog_assessment_captures_provider_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = local_feedback._LocalFeedbackAdapter()
    adapter._text_model = "openai/mistral-small-latest"
    lm = object()
    monkeypatch.setattr(adapter, "_get_text_analysis_lm", lambda: lm)
    monkeypatch.setattr(
        dialog_assessment_program,
        "analyze_dialog",
        lambda **_kwargs: FeedbackResult(feedback_md="Rückmeldung", analysis_json={}),
    )
    event = TokenUsageEvent(
        event_key="00000000-0000-0000-0000-000000000111",
        model="openai/mistral-small-latest",
        stage="analysis",
        modality="text",
        call_kind="primary",
        usage_known=True,
        input_tokens=23,
        output_tokens=5,
        total_tokens=28,
    )
    capture_args: dict[str, object] = {}

    def _capture(operation, **kwargs):  # type: ignore[no-untyped-def]
        capture_args.update(kwargs)
        return operation(), [event]

    monkeypatch.setattr(local_feedback, "capture_dspy_usage", _capture, raising=False)

    result = adapter.analyze_dialog(
        student_performance={"turns": []},
        conversation_context={"turns": []},
        criteria=[],
        instruction_md="Führe den Dialog.",
    )

    assert result.usage_events == [event]
    assert capture_args == {
        "model": "openai/mistral-small-latest",
        "stage": "analysis",
        "modality": "text",
        "call_kind": "primary",
    }


def test_dialog_assessment_transports_captured_usage_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = local_feedback._LocalFeedbackAdapter()
    adapter._text_model = "openai/mistral-small-latest"
    monkeypatch.setattr(adapter, "_get_text_analysis_lm", lambda: object())
    event = TokenUsageEvent(
        event_key="00000000-0000-0000-0000-000000000222",
        model="openai/mistral-small-latest",
        stage="analysis",
        modality="text",
        call_kind="primary",
        usage_known=False,
        unknown_reason="missing_provider_usage",
    )

    def _capture_failure(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        exc = RuntimeError("provider failed after request")
        exc.usage_events = [event]  # type: ignore[attr-defined]
        raise exc

    monkeypatch.setattr(local_feedback, "capture_dspy_usage", _capture_failure)

    with pytest.raises(FeedbackTransientError) as raised:
        adapter.analyze_dialog(
            student_performance={"turns": []},
            conversation_context={"turns": []},
            criteria=[],
            instruction_md="Führe den Dialog.",
        )

    assert raised.value.usage_events == [event]
