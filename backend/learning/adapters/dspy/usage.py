"""DSPy usage capture for Learning adapters.

Why:
    Token usage is provider telemetry, not pedagogical content. This helper
    extracts only technical counters from DSPy's tracker and converts them into
    persistence-ready events without keeping raw provider payloads.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar
from uuid import uuid4

from backend.learning.adapters.ports import TokenUsageEvent

T = TypeVar("T")


def _int_or_none(value: object) -> int | None:
    try:
        if value is None:
            return None
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _event_from_usage(
    *,
    model: str,
    usage: dict[str, object],
    stage: str,
    modality: str,
    call_kind: str,
) -> TokenUsageEvent | None:
    input_tokens = _int_or_none(usage.get("prompt_tokens"))
    output_tokens = _int_or_none(usage.get("completion_tokens"))
    total_tokens = _int_or_none(usage.get("total_tokens"))
    if input_tokens is None and output_tokens is None and total_tokens is None:
        return None
    return TokenUsageEvent(
        event_key=str(uuid4()),
        model=str(model or "unknown"),
        stage=stage,
        modality=modality,
        call_kind=call_kind,
        usage_known=True,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def _events_from_tracker(
    tracker: object,
    *,
    fallback_model: str,
    stage: str,
    modality: str,
    call_kind: str,
) -> list[TokenUsageEvent]:
    usage_data = getattr(tracker, "usage_data", None)
    if not isinstance(usage_data, dict):
        return []

    events: list[TokenUsageEvent] = []
    for model, entries in usage_data.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            event = _event_from_usage(
                model=str(model or fallback_model or "unknown"),
                usage=entry,
                stage=stage,
                modality=modality,
                call_kind=call_kind,
            )
            if event is not None:
                events.append(event)
    return events


def capture_dspy_usage(
    operation: Callable[[], T],
    *,
    model: str,
    stage: str,
    modality: str,
    call_kind: str,
) -> tuple[T, list[TokenUsageEvent]]:
    """Run a DSPy operation and return its result plus tracked token events.

    Permissions:
        This helper performs no persistence. The learning worker later stores
        events through its restricted database helper.
    """
    import dspy  # type: ignore

    if not hasattr(dspy, "track_usage"):
        return operation(), []

    with dspy.track_usage() as tracker:  # type: ignore[attr-defined]
        try:
            result = operation()
        except Exception as exc:
            events = _events_from_tracker(
                tracker,
                fallback_model=model,
                stage=stage,
                modality=modality,
                call_kind=call_kind,
            )
            if events:
                try:
                    setattr(exc, "usage_events", events)
                except Exception:
                    pass
            raise
    events = _events_from_tracker(
        tracker,
        fallback_model=model,
        stage=stage,
        modality=modality,
        call_kind=call_kind,
    )
    return result, events
