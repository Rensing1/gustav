"""Usage-accounting tests for the local dialog generator."""

from __future__ import annotations

import pytest

from backend.learning.adapters import local_dialog


def test_dialog_failure_creates_content_free_usage_event(monkeypatch: pytest.MonkeyPatch) -> None:
    generator = local_dialog.LocalDialogGenerator()
    monkeypatch.setattr(
        generator,
        "_get_lm",
        lambda: (_ for _ in ()).throw(RuntimeError("provider secret must not be persisted")),
    )

    with pytest.raises(RuntimeError):
        generator.initial_starters(context={})

    events = generator.pop_usage_events()
    assert len(events) == 1
    assert events[0].error_code == "dialog_ai_unavailable"
    assert events[0].usage_known is False
    assert "provider secret" not in repr(events[0])


def test_missing_provider_counters_still_create_usage_event(monkeypatch: pytest.MonkeyPatch) -> None:
    generator = local_dialog.LocalDialogGenerator()
    monkeypatch.setattr(generator, "_get_lm", lambda: object())
    monkeypatch.setattr(
        local_dialog,
        "capture_dspy_usage",
        lambda operation, **kwargs: (["Ich vermute …"], []),
    )

    assert generator.initial_starters(context={}) == ["Ich vermute …"]

    events = generator.pop_usage_events()
    assert len(events) == 1
    assert events[0].error_code is None
    assert events[0].unknown_reason == "missing_provider_usage"
