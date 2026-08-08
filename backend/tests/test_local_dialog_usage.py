"""Usage-accounting tests for the local dialog generator."""

from __future__ import annotations

import pytest

from backend.learning.adapters import local_dialog


def test_dialog_failure_before_provider_call_creates_no_usage_event(monkeypatch: pytest.MonkeyPatch) -> None:
    generator = local_dialog.LocalDialogGenerator()
    monkeypatch.setattr(
        generator,
        "_get_lm",
        lambda: (_ for _ in ()).throw(RuntimeError("provider secret must not be persisted")),
    )

    with pytest.raises(RuntimeError):
        generator.initial_starters(context={})

    assert generator.pop_usage_events() == []


def test_empty_tracker_does_not_invent_usage_for_possible_cache_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    generator = local_dialog.LocalDialogGenerator()
    monkeypatch.setattr(generator, "_get_lm", lambda: object())
    monkeypatch.setattr(
        local_dialog,
        "capture_dspy_usage",
        lambda operation, **kwargs: (["Ich vermute …"], []),
    )

    assert generator.initial_starters(context={}) == ["Ich vermute …"]

    assert generator.pop_usage_events() == []
