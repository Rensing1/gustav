"""DSPy dialog generator using the existing OpenAI-compatible text model."""

from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

from backend.learning.adapters.dspy import dialog_program
from backend.learning.adapters.dspy import helpers as dspy_helpers
from backend.learning.adapters.dspy.usage import capture_dspy_usage
from backend.learning.adapters.local_feedback import _require_secure_openai_base_url
from backend.learning.adapters.ports import TokenUsageEvent


def _model_name(raw: str) -> str:
    value = raw.strip()
    if not value or "/" in value:
        return value
    return f"openai/{value}"


class LocalDialogGenerator:
    """Generate stateless dialog output without tools, browsing or memory."""

    def __init__(self) -> None:
        self._base_url = (os.getenv("OPENAI_BASE_URL") or "").strip()
        self._api_key = (os.getenv("OPENAI_API_KEY") or "").strip() or "sk-noop"
        self._model = _model_name(os.getenv("AI_TEXT_MODEL") or "")
        self._lm = None
        self._usage_events: list[Any] = []

    def _unknown_usage(self, *, stage: str, error_code: str | None = None) -> TokenUsageEvent:
        """Create one content-free event when provider telemetry is unavailable."""

        return TokenUsageEvent(
            event_key=str(uuid4()),
            model=self._model or "unknown",
            stage=stage,
            modality="text",
            call_kind="dialog_generation",
            usage_known=False,
            unknown_reason="missing_provider_usage",
            error_code=error_code,
        )

    def _captured_events(self, events: list[Any], *, stage: str) -> list[Any]:
        return events or [self._unknown_usage(stage=stage)]

    def _failed_events(self, exc: Exception, *, stage: str) -> list[Any]:
        events = list(getattr(exc, "usage_events", []) or [])
        if not events:
            return [self._unknown_usage(stage=stage, error_code="dialog_ai_unavailable")]
        for event in events:
            event.error_code = "dialog_ai_unavailable"
        return events

    def _get_lm(self):  # type: ignore[no-untyped-def]
        if self._lm is not None:
            return self._lm
        if not self._base_url or not self._model:
            raise RuntimeError("dialog_ai_unavailable")
        _require_secure_openai_base_url(self._base_url)
        import dspy  # type: ignore

        kwargs: dict[str, Any] = {
            "base_url": self._base_url,
            "api_key": self._api_key,
            "temperature": float(os.getenv("AI_TEXT_TEMPERATURE") or "0"),
            "num_retries": 0,
        }
        think = dspy_helpers.resolve_think_level(self._model, os.getenv("AI_TEXT_THINK_LEVEL"))
        if think:
            kwargs["extra_body"] = {"think": think}
        effort = dspy_helpers.resolve_reasoning_effort(self._model, os.getenv("AI_TEXT_REASONING_EFFORT"))
        if effort:
            kwargs["reasoning_effort"] = effort
        self._lm = dspy.LM(self._model, **kwargs)
        return self._lm

    def initial_starters(self, *, context: dict[str, Any]) -> list[str]:
        try:
            lm = self._get_lm()
            result, events = capture_dspy_usage(
                lambda: dialog_program.initial_starters(context=context, lm=lm),
                model=self._model,
                stage="initial_starters",
                modality="text",
                call_kind="dialog_generation",
            )
        except Exception as exc:
            self._usage_events = self._failed_events(exc, stage="initial_starters")
            raise
        self._usage_events = self._captured_events(events, stage="initial_starters")
        return result

    def partner_reply(self, *, context: dict[str, Any], turn: dict[str, Any]) -> dict[str, Any]:
        try:
            lm = self._get_lm()
            result, events = capture_dspy_usage(
                lambda: dialog_program.partner_reply(context=context, turn=turn, lm=lm),
                model=self._model,
                stage="reply",
                modality="text",
                call_kind="dialog_generation",
            )
        except Exception as exc:
            self._usage_events = self._failed_events(exc, stage="reply")
            raise
        self._usage_events = self._captured_events(events, stage="reply")
        return result

    def pop_usage_events(self) -> list[Any]:
        events, self._usage_events = self._usage_events, []
        return events


def build() -> LocalDialogGenerator:
    return LocalDialogGenerator()
