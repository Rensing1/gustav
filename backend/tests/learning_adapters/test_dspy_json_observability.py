"""
Unit tests for DSPy JSON observability helpers.

Intent:
    Make the internal `response_format` decision visible without performing
    real network calls.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.learning.adapters.dspy import json_observability
from backend.learning.adapters.dspy.signatures import FeedbackAnalysisSignature


def test_instrumented_adapter_marks_json_schema_when_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    import dspy.adapters.chat_adapter as chat_adapter

    adapter = json_observability.build_json_adapter(stage="analysis")
    lm = SimpleNamespace(model="openai/mistral-small-4")

    monkeypatch.setattr(
        "litellm.get_supported_openai_params",
        lambda **_kwargs: ["response_format", "temperature"],
    )
    monkeypatch.setattr(chat_adapter.ChatAdapter, "__call__", lambda *args, **kwargs: [{"ok": True}])

    json_observability.clear_last_call_metadata()
    _ = adapter(  # type: ignore[operator]
        lm,
        {"reasoning_effort": "none"},
        FeedbackAnalysisSignature,
        [],
        {"student_text_md": "Antwort", "criteria": ["Inhalt"]},
    )

    meta = json_observability.pop_last_call_metadata()
    assert meta is not None
    assert meta["stage"] == "analysis"
    assert meta["response_format_mode"] == "json_schema"
    assert meta["reasoning_effort"] == "none"


def test_instrumented_adapter_marks_json_object_fallback_when_schema_build_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dspy.adapters.chat_adapter as chat_adapter

    adapter = json_observability.build_json_adapter(stage="analysis")
    lm = SimpleNamespace(model="openai/mistral-small-4")

    monkeypatch.setattr(
        "litellm.get_supported_openai_params",
        lambda **_kwargs: ["response_format", "temperature"],
    )
    monkeypatch.setattr(
        json_observability,
        "_get_structured_outputs_response_format",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("broken schema")),
    )
    monkeypatch.setattr(chat_adapter.ChatAdapter, "__call__", lambda *args, **kwargs: [{"ok": True}])

    json_observability.clear_last_call_metadata()
    _ = adapter(  # type: ignore[operator]
        lm,
        {},
        FeedbackAnalysisSignature,
        [],
        {"student_text_md": "Antwort", "criteria": ["Inhalt"]},
    )

    meta = json_observability.pop_last_call_metadata()
    assert meta is not None
    assert meta["response_format_mode"] == "json_object_fallback"

