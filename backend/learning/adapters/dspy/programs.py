"""DSPy program scaffolding for learning feedback (analysis → synthesis)."""

from __future__ import annotations

from typing import Any, Callable, Sequence

from backend.learning.adapters.dspy.signatures import (
    FeedbackAnalysisSignature,
    FeedbackNoCriteriaSignature,
    FeedbackSynthesisSignature,
    VisualFeedbackAnalysisSignature,
    VisualFeedbackNoCriteriaSignature,
    VisualFeedbackSynthesisSignature,
)
from backend.learning.adapters.dspy.types import CriteriaAnalysis, CriterionResult


def _ensure_criteria_results(value: Any) -> list[CriterionResult]:
    if value is None:
        return []
    if isinstance(value, list):
        return [CriterionResult.from_value(item) for item in value]
    return [CriterionResult.from_value(value)]


def run_structured_analysis(
    *,
    text_md: str,
    criteria: Sequence[str],
    teacher_instructions_md: str | None = None,
    teacher_context_md: str | None = None,
) -> CriteriaAnalysis:
    """Execute DSPy Predict(Signature) to obtain structured analysis data."""
    try:  # pragma: no cover - exercised via tests
        import dspy  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise ImportError(f"dspy unavailable: {exc}")

    predict = dspy.Predict(FeedbackAnalysisSignature)  # type: ignore[attr-defined]
    out = predict(
        student_text_md=text_md,
        criteria=list(criteria),
        teacher_instructions_md=teacher_instructions_md,
        teacher_context_md=teacher_context_md,
    )
    score_value = getattr(out, "overall_score", 0)
    try:
        score_int = int(score_value) if score_value is not None else 0
    except Exception:
        score_int = 0
    return CriteriaAnalysis(
        schema="criteria.v2",
        score=score_int,
        criteria_results=_ensure_criteria_results(getattr(out, "criteria_results", [])),
    )


def run_structured_feedback(
    *,
    text_md: str,
    criteria: Sequence[str],
    analysis_json: CriteriaAnalysis | dict[str, Any],
    teacher_instructions_md: str | None = None,
    teacher_context_md: str | None = None,
) -> str:
    """Execute DSPy Predict(Signature) to obtain feedback prose."""
    try:  # pragma: no cover
        import dspy  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise ImportError(f"dspy unavailable: {exc}")

    payload = analysis_json.to_dict() if isinstance(analysis_json, CriteriaAnalysis) else analysis_json
    predict = dspy.Predict(FeedbackSynthesisSignature)  # type: ignore[attr-defined]
    out = predict(
        student_text_md=text_md,
        analysis_json=payload,
        teacher_instructions_md=teacher_instructions_md,
        teacher_context_md=teacher_context_md,
    )
    val = getattr(out, "feedback_md", None)
    if isinstance(val, str) and val.strip() and val.strip().lower() != "none":
        return val
    raise RuntimeError("empty_feedback_md")


def run_feedback_no_criteria(
    *,
    text_md: str,
    teacher_instructions_md: str | None = None,
    teacher_context_md: str | None = None,
) -> str:
    """Execute DSPy Predict(Signature) to obtain feedback prose without criteria."""
    try:  # pragma: no cover
        import dspy  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise ImportError(f"dspy unavailable: {exc}")

    predict = dspy.Predict(FeedbackNoCriteriaSignature)  # type: ignore[attr-defined]
    out = predict(
        student_text_md=text_md,
        teacher_instructions_md=teacher_instructions_md,
        teacher_context_md=teacher_context_md,
    )
    val = getattr(out, "feedback_md", None)
    if isinstance(val, str) and val.strip() and val.strip().lower() != "none":
        return val
    raise RuntimeError("empty_feedback_md")


def run_structured_visual_analysis(
    *,
    image_data_uri: str,
    criteria: Sequence[str],
    teacher_instructions_md: str | None = None,
    teacher_context_md: str | None = None,
) -> CriteriaAnalysis:
    """Execute DSPy Predict(Signature) to obtain structured analysis from an image."""
    try:  # pragma: no cover - exercised via tests
        import dspy  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise ImportError(f"dspy unavailable: {exc}")

    img = dspy.Image(url=str(image_data_uri))  # type: ignore[attr-defined]
    predict = dspy.Predict(VisualFeedbackAnalysisSignature)  # type: ignore[attr-defined]
    out = predict(
        student_image=img,
        criteria=list(criteria),
        teacher_instructions_md=teacher_instructions_md,
        teacher_context_md=teacher_context_md,
    )
    score_value = getattr(out, "overall_score", 0)
    try:
        score_int = int(score_value) if score_value is not None else 0
    except Exception:
        score_int = 0
    return CriteriaAnalysis(
        schema="criteria.v2",
        score=score_int,
        criteria_results=_ensure_criteria_results(getattr(out, "criteria_results", [])),
    )


def run_structured_visual_feedback(
    *,
    image_data_uri: str,
    criteria: Sequence[str],
    analysis_json: CriteriaAnalysis | dict[str, Any],
    teacher_instructions_md: str | None = None,
    teacher_context_md: str | None = None,
) -> str:
    """Execute DSPy Predict(Signature) to obtain feedback prose from an image."""
    try:  # pragma: no cover
        import dspy  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise ImportError(f"dspy unavailable: {exc}")

    img = dspy.Image(url=str(image_data_uri))  # type: ignore[attr-defined]
    payload = analysis_json.to_dict() if isinstance(analysis_json, CriteriaAnalysis) else analysis_json
    predict = dspy.Predict(VisualFeedbackSynthesisSignature)  # type: ignore[attr-defined]
    out = predict(
        student_image=img,
        analysis_json=payload,
        teacher_instructions_md=teacher_instructions_md,
        teacher_context_md=teacher_context_md,
    )
    val = getattr(out, "feedback_md", None)
    if isinstance(val, str) and val.strip() and val.strip().lower() != "none":
        return val
    raise RuntimeError("empty_feedback_md")


def run_visual_feedback_no_criteria(
    *,
    image_data_uri: str,
    teacher_instructions_md: str | None = None,
    teacher_context_md: str | None = None,
) -> str:
    """Execute DSPy Predict(Signature) to obtain visual feedback prose without criteria."""
    try:  # pragma: no cover
        import dspy  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise ImportError(f"dspy unavailable: {exc}")

    img = dspy.Image(url=str(image_data_uri))  # type: ignore[attr-defined]
    predict = dspy.Predict(VisualFeedbackNoCriteriaSignature)  # type: ignore[attr-defined]
    out = predict(
        student_image=img,
        teacher_instructions_md=teacher_instructions_md,
        teacher_context_md=teacher_context_md,
    )
    val = getattr(out, "feedback_md", None)
    if isinstance(val, str) and val.strip() and val.strip().lower() != "none":
        return val
    raise RuntimeError("empty_feedback_md")


class FeedbackAnalysisProgram:
    """Lightweight runner facade for the legacy single-step analysis prompt."""

    def __init__(self, *, runner: Callable[..., str]):
        self._runner = runner

    def run(
        self,
        *,
        text_md: str,
        criteria: Sequence[str],
        teacher_instructions_md: str | None = None,
        teacher_context_md: str | None = None,
    ) -> str:
        import inspect as _inspect
        kwargs = {"text_md": text_md, "criteria": criteria}
        try:
            sig = _inspect.signature(self._runner)
            if "teacher_instructions_md" in sig.parameters:
                kwargs["teacher_instructions_md"] = teacher_instructions_md
            if "teacher_context_md" in sig.parameters:
                kwargs["teacher_context_md"] = teacher_context_md
        except Exception:
            pass
        return self._runner(**kwargs)


class FeedbackSynthesisProgram:
    """Wrapper around the feedback-synthesis runner (second DSPy stage)."""

    def __init__(self, *, runner: Callable[..., str]):
        self._runner = runner

    def run(
        self,
        *,
        text_md: str,
        criteria: Sequence[str],
        analysis_json: dict[str, Any],
        teacher_instructions_md: str | None = None,
    ) -> str:
        import inspect as _inspect
        kwargs = {"text_md": text_md, "criteria": criteria, "analysis_json": analysis_json}
        try:
            sig = _inspect.signature(self._runner)
            if "teacher_instructions_md" in sig.parameters:
                kwargs["teacher_instructions_md"] = teacher_instructions_md
        except Exception:
            pass
        return self._runner(**kwargs)
