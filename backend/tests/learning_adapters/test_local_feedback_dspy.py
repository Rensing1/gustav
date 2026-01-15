"""
Local feedback adapter: DSPy-only (no legacy backend fallback).

Contract:
    - Requires `OPENAI_BASE_URL` and `AI_TEXT_MODEL`.
    - Uses `dspy.context(...)` (thread-local) instead of `dspy.configure(...)`.
    - Does not require any Ollama-specific client/library.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from backend.learning.adapters.ports import FeedbackPermanentError, FeedbackResult, FeedbackTransientError


def _install_fake_dspy(monkeypatch: pytest.MonkeyPatch, *, observed: dict) -> None:
    class _FakeLM:  # noqa: D401 - tiny stub
        def __init__(self, model: str, **kwargs) -> None:
            observed.setdefault("lm_calls", []).append({"model": model, "kwargs": dict(kwargs)})

    class _FakeJSONAdapter:
        pass

    @contextmanager
    def _ctx(**kwargs):  # type: ignore[no-untyped-def]
        observed.setdefault("contexts", []).append(dict(kwargs))
        yield

    monkeypatch.setitem(
        sys.modules,
        "dspy",
        SimpleNamespace(
            __version__="0.0-test",
            LM=_FakeLM,
            JSONAdapter=_FakeJSONAdapter,
            context=_ctx,
        ),
    )


def test_adapter_requires_openai_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.learning.adapters import local_feedback

    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("AI_TEXT_MODEL", "gpt-4o")

    adapter = local_feedback.build()
    with pytest.raises(FeedbackTransientError, match="missing_OPENAI_BASE_URL"):
        adapter.analyze(text_md="Antwort", criteria=["K1"])  # type: ignore[arg-type]


def test_adapter_builds_lm_with_base_url_as_is(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.learning.adapters import local_feedback

    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("OPENAI_BASE_URL", "http://100.80.221.81:8111/api/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("AI_TEXT_MODEL", "my-model")
    monkeypatch.setenv("AI_TEXT_TEMPERATURE", "0.25")

    # Stub the DSPy program call to avoid needing real Predict.
    from backend.learning.adapters.dspy import feedback_program

    monkeypatch.setattr(
        feedback_program,
        "analyze_feedback",
        lambda **_: FeedbackResult(
            feedback_md="**Das ist dir gut gelungen:** A.\n\n**Das kannst du besser:** B.",
            analysis_json={"schema": "criteria.v2", "score": 0, "criteria_results": []},
            parse_status="parsed_structured",
        ),
    )

    adapter = local_feedback.build()
    res = adapter.analyze(text_md="Antwort", criteria=["K1"])  # type: ignore[arg-type]
    assert res.feedback_md.startswith("**Das ist dir gut gelungen:**")

    lm_calls = observed.get("lm_calls") or []
    assert lm_calls, "Expected LM to be instantiated"
    lm_kwargs = lm_calls[0]["kwargs"]
    assert lm_kwargs["base_url"] == "http://100.80.221.81:8111/api/v1"
    assert lm_kwargs["temperature"] == 0.25

    contexts = observed.get("contexts") or []
    assert contexts, "Expected dspy.context(...) usage"
    assert contexts[0].get("disable_history") is True


def test_adapter_analyze_visual_requires_visual_model(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.learning.adapters import local_feedback

    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("OPENAI_BASE_URL", "http://example/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "t-model")
    monkeypatch.delenv("AI_VISUAL_MODEL", raising=False)

    adapter = local_feedback.build()
    with pytest.raises(FeedbackPermanentError, match="missing_AI_VISUAL_MODEL"):
        adapter.analyze_visual(  # type: ignore[attr-defined]
            submission={"id": "s", "kind": "image", "mime_type": "image/png", "course_id": "c", "task_id": "t", "student_sub": "u"},
            job_payload={"mime_type": "image/png"},
            criteria=["K1"],
            instruction_md="Aufgabe",
            teacher_context_md=None,
        )
