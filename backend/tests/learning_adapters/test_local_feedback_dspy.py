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

from backend.learning.adapters.ports import (
    FeedbackInvalidAnalysisError,
    FeedbackPermanentError,
    FeedbackResult,
    FeedbackTransientError,
)


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


def test_prod_allows_http_openai_base_url_for_remote_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.learning.adapters import local_feedback

    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example.com/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "t-model")

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
    assert lm_calls[0]["kwargs"]["base_url"] == "http://example.com/api/v1"


def test_prod_allows_http_openai_base_url_for_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.learning.adapters import local_feedback

    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "t-model")

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
    assert lm_calls[0]["kwargs"]["base_url"] == "http://127.0.0.1:11434/v1"


def test_prod_allows_http_openai_base_url_for_host_docker_internal(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.learning.adapters import local_feedback

    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://host.docker.internal:8111/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "t-model")

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
    assert lm_calls[0]["kwargs"]["base_url"] == "http://host.docker.internal:8111/api/v1"


def test_prod_allows_http_openai_base_url_for_private_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.learning.adapters import local_feedback

    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://10.0.0.23:11434/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "t-model")

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
    assert lm_calls[0]["kwargs"]["base_url"] == "http://10.0.0.23:11434/v1"


def test_adapter_builds_lm_with_base_url_as_is(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.learning.adapters import local_feedback

    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("OPENAI_BASE_URL", "http://example/api/v1")
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
    assert lm_kwargs["base_url"] == "http://example/api/v1"
    assert lm_kwargs["temperature"] == 0.25

def test_adapter_uses_analysis_and_synthesis_text_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.learning.adapters import local_feedback

    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("OPENAI_BASE_URL", "http://example/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "gpt-oss:120b")
    monkeypatch.setenv("AI_TEXT_TEMPERATURE", "0.25")
    monkeypatch.setenv("AI_TEXT_ANALYSIS_TEMPERATURE", "0.05")
    monkeypatch.setenv("AI_TEXT_SYNTHESIS_TEMPERATURE", "0.75")
    monkeypatch.setenv("AI_TEXT_ANALYSIS_THINK_LEVEL", "low")
    monkeypatch.setenv("AI_TEXT_SYNTHESIS_THINK_LEVEL", "high")

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
    _ = adapter.analyze(text_md="Antwort", criteria=["K1"])  # type: ignore[arg-type]

    lm_calls = observed.get("lm_calls") or []
    assert len(lm_calls) == 2
    analysis_kwargs = lm_calls[0]["kwargs"]
    synthesis_kwargs = lm_calls[1]["kwargs"]
    assert analysis_kwargs["temperature"] == 0.05
    assert synthesis_kwargs["temperature"] == 0.75
    assert analysis_kwargs.get("extra_body", {}).get("think") == "low"
    assert synthesis_kwargs.get("extra_body", {}).get("think") == "high"


def test_adapter_sanitizes_unexpected_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Security regression: the adapter must not surface raw exception messages.

    Why:
        Upstream LLM/SDK exceptions may contain request payloads (student text).
        We only propagate stable error codes.
    """
    from backend.learning.adapters import local_feedback

    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("OPENAI_BASE_URL", "http://example/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "t-model")

    from backend.learning.adapters.dspy import feedback_program

    def _boom(**_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("studentPII: leaked payload")

    monkeypatch.setattr(feedback_program, "analyze_feedback", _boom)

    adapter = local_feedback.build()
    with pytest.raises(FeedbackTransientError) as exc:
        adapter.analyze(text_md="Antwort", criteria=["K1"])  # type: ignore[arg-type]
    assert str(exc.value) == "feedback_failed"


def test_adapter_maps_invalid_criterion_idx_to_permanent_invalid_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deterministic schema errors must not be surfaced as retryable feedback failures."""
    from backend.learning.adapters import local_feedback

    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("OPENAI_BASE_URL", "http://example/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "t-model")

    from backend.learning.adapters.dspy import feedback_program

    def _boom(**_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("invalid_criterion_idx")

    monkeypatch.setattr(feedback_program, "analyze_feedback", _boom)

    adapter = local_feedback.build()
    with pytest.raises(FeedbackInvalidAnalysisError) as exc:
        adapter.analyze(text_md="Antwort", criteria=["K1"])  # type: ignore[arg-type]
    assert str(exc.value) == "feedback_invalid_analysis"


def test_adapter_maps_invalid_criterion_idx_with_context_to_permanent_invalid_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mapping must survive small message variations from the DSPy layer."""
    from backend.learning.adapters import local_feedback

    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("OPENAI_BASE_URL", "http://example/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "t-model")

    from backend.learning.adapters.dspy import feedback_program

    def _boom(**_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("invalid_criterion_idx: criterion 2 missing")

    monkeypatch.setattr(feedback_program, "analyze_feedback", _boom)

    adapter = local_feedback.build()
    with pytest.raises(FeedbackInvalidAnalysisError) as exc:
        adapter.analyze(text_md="Antwort", criteria=["K1"])  # type: ignore[arg-type]
    assert str(exc.value) == "feedback_invalid_analysis"


def test_adapter_maps_invalid_analysis_json_to_permanent_invalid_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Structured-analysis shape errors are deterministic and must not retry."""
    from backend.learning.adapters import local_feedback

    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("OPENAI_BASE_URL", "http://example/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "t-model")

    from backend.learning.adapters.dspy import feedback_program

    def _boom(**_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("invalid_analysis_json")

    monkeypatch.setattr(feedback_program, "analyze_feedback", _boom)

    adapter = local_feedback.build()
    with pytest.raises(FeedbackInvalidAnalysisError) as exc:
        adapter.analyze(text_md="Antwort", criteria=["K1"])  # type: ignore[arg-type]
    assert str(exc.value) == "feedback_invalid_analysis"


def test_adapter_maps_invalid_feedback_format_to_permanent_feedback_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deterministic feedback-format violations must not be retried forever."""
    from backend.learning.adapters import local_feedback

    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("OPENAI_BASE_URL", "http://example/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "t-model")

    from backend.learning.adapters.dspy import feedback_program

    def _boom(**_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("invalid_feedback_format")

    monkeypatch.setattr(feedback_program, "analyze_feedback", _boom)

    adapter = local_feedback.build()
    with pytest.raises(FeedbackPermanentError) as exc:
        adapter.analyze(text_md="Antwort", criteria=["K1"])  # type: ignore[arg-type]
    assert str(exc.value) == "invalid_feedback_format"


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


def test_adapter_sets_text_think_level_low_for_gpt_oss_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    GPT-OSS models must receive an explicit think level to avoid long traces.

    This is intentionally conservative: only GPT-OSS gets a think level; all
    other models remain unchanged.
    """
    from backend.learning.adapters import local_feedback

    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("OPENAI_BASE_URL", "http://example/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "gpt-oss:120b")
    monkeypatch.delenv("AI_TEXT_THINK_LEVEL", raising=False)

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
    _ = adapter.analyze(text_md="Antwort", criteria=["K1"])  # type: ignore[arg-type]

    lm_calls = observed.get("lm_calls") or []
    assert lm_calls, "Expected LM to be instantiated"
    lm_kwargs = lm_calls[0]["kwargs"]
    assert lm_kwargs.get("extra_body", {}).get("think") == "low"


def test_adapter_ignores_text_think_level_for_non_gpt_oss(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Safety: non-GPT-OSS models must never receive a think level, even if set.
    """
    from backend.learning.adapters import local_feedback

    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("OPENAI_BASE_URL", "http://example/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "llama3.1")
    monkeypatch.setenv("AI_TEXT_THINK_LEVEL", "high")

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
    _ = adapter.analyze(text_md="Antwort", criteria=["K1"])  # type: ignore[arg-type]

    lm_calls = observed.get("lm_calls") or []
    assert lm_calls, "Expected LM to be instantiated"
    lm_kwargs = lm_calls[0]["kwargs"]
    assert "extra_body" not in lm_kwargs


def test_adapter_sets_visual_think_level_low_for_gpt_oss_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Visual LM construction should also apply the GPT-OSS think-level default.
    """
    from backend.learning.adapters import local_feedback

    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("OPENAI_BASE_URL", "http://example/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "t-model")
    monkeypatch.setenv("AI_VISUAL_MODEL", "gpt-oss:120b")
    monkeypatch.delenv("AI_VISUAL_THINK_LEVEL", raising=False)

    adapter = local_feedback.build()
    with pytest.raises(FeedbackPermanentError, match="unsupported_mime"):
        adapter.analyze_visual(  # type: ignore[attr-defined]
            submission={"id": "s"},
            job_payload={"mime_type": "application/zip"},
            criteria=["K1"],
            instruction_md=None,
            teacher_context_md=None,
        )

    lm_calls = observed.get("lm_calls") or []
    assert lm_calls, "Expected visual LM to be instantiated"
    lm_kwargs = lm_calls[0]["kwargs"]
    assert lm_kwargs.get("extra_body", {}).get("think") == "low"


def test_adapter_uses_analysis_and_synthesis_visual_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.learning.adapters import local_feedback

    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("OPENAI_BASE_URL", "http://example/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "t-model")
    monkeypatch.setenv("AI_VISUAL_MODEL", "gpt-oss:120b")
    monkeypatch.setenv("AI_VISUAL_TEMPERATURE", "0.2")
    monkeypatch.setenv("AI_VISUAL_ANALYSIS_TEMPERATURE", "0.0")
    monkeypatch.setenv("AI_VISUAL_SYNTHESIS_TEMPERATURE", "0.6")
    monkeypatch.setenv("AI_VISUAL_ANALYSIS_THINK_LEVEL", "low")
    monkeypatch.setenv("AI_VISUAL_SYNTHESIS_THINK_LEVEL", "high")

    from backend.learning.adapters import local_vision
    from backend.learning.adapters.dspy import visual_feedback_program

    monkeypatch.setattr(local_vision, "_resolve_submission_image_bytes", lambda **_: "AA==")
    monkeypatch.setattr(
        visual_feedback_program,
        "analyze_visual_feedback",
        lambda **_: FeedbackResult(
            feedback_md="**Das ist dir gut gelungen:** A.\n\n**Das kannst du besser:** B.",
            analysis_json={"schema": "criteria.v2", "score": 0, "criteria_results": []},
            parse_status="parsed_structured",
        ),
    )

    adapter = local_feedback.build()
    _ = adapter.analyze_visual(  # type: ignore[attr-defined]
        submission={"id": "s", "kind": "image", "mime_type": "image/png"},
        job_payload={"mime_type": "image/png"},
        criteria=["K1"],
        instruction_md=None,
        teacher_context_md=None,
    )

    lm_calls = observed.get("lm_calls") or []
    assert len(lm_calls) == 2
    analysis_kwargs = lm_calls[0]["kwargs"]
    synthesis_kwargs = lm_calls[1]["kwargs"]
    assert analysis_kwargs["temperature"] == 0.0
    assert synthesis_kwargs["temperature"] == 0.6
    assert analysis_kwargs.get("extra_body", {}).get("think") == "low"
    assert synthesis_kwargs.get("extra_body", {}).get("think") == "high"


def test_adapter_uses_mistral_reasoning_effort_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.learning.adapters import local_feedback

    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("OPENAI_BASE_URL", "http://example/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "mistral-small-4")
    monkeypatch.setenv("AI_TEXT_REASONING_EFFORT", "high")
    monkeypatch.setenv("AI_TEXT_ANALYSIS_REASONING_EFFORT", "none")
    monkeypatch.setenv("AI_TEXT_SYNTHESIS_REASONING_EFFORT", "high")

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
    _ = adapter.analyze(text_md="Antwort", criteria=["K1"])  # type: ignore[arg-type]

    lm_calls = observed.get("lm_calls") or []
    assert len(lm_calls) == 2
    assert lm_calls[0]["kwargs"]["reasoning_effort"] == "none"
    assert lm_calls[1]["kwargs"]["reasoning_effort"] == "high"


def test_visual_feedback_program_uses_separate_lms_when_provided(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "dspy", SimpleNamespace(__version__="3.0.3"))
    from backend.learning.adapters.dspy import visual_feedback_program

    observed: list[dict] = []

    @contextmanager
    def _ctx(**kwargs):  # type: ignore[no-untyped-def]
        observed.append(dict(kwargs))
        yield

    monkeypatch.setitem(
        sys.modules,
        "dspy",
        SimpleNamespace(__version__="0.0-test", context=_ctx, JSONAdapter=object),
    )

    from backend.learning.adapters.dspy import programs

    monkeypatch.setattr(
        programs,
        "run_structured_visual_analysis",
        lambda **_: {"schema": "criteria.v2", "score": 3, "criteria_results": [{"criterion": "K1", "score": 5, "max_score": 10, "explanation_md": "ok"}]},
        raising=False,
    )
    monkeypatch.setattr(
        programs,
        "run_structured_visual_feedback",
        lambda **_: "**Das ist dir gut gelungen:** A.\n\n**Das kannst du besser:** B.",
        raising=False,
    )

    analysis_lm = object()
    synthesis_lm = object()
    result = visual_feedback_program.analyze_visual_feedback(  # type: ignore[attr-defined]
        image_data_uri="data:image/png;base64,AA==",
        criteria=["K1"],
        teacher_instructions_md="Aufgabe",
        teacher_context_md=None,
        analysis_lm=analysis_lm,
        synthesis_lm=synthesis_lm,
    )

    assert result.parse_status == "parsed_structured"
    assert observed[0]["lm"] is analysis_lm
    assert observed[1]["lm"] is synthesis_lm
