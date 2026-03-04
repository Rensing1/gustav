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
from backend.learning.adapters.dspy.types import CriteriaAnalysis, CriterionResult, LeanCriterionResult


def _ensure_lean_criteria_results(value: Any) -> list[LeanCriterionResult]:
    if value is None:
        return []
    try:
        if isinstance(value, list):
            return [LeanCriterionResult.from_value(item) for item in value]
        return [LeanCriterionResult.from_value(value)]
    except ValueError as exc:
        raise RuntimeError("invalid_criterion_idx") from exc


def _map_lean_results_to_criteria(
    *,
    criteria: Sequence[str],
    lean_results: list[LeanCriterionResult],
    default_explanation_md: str,
) -> list[CriterionResult]:
    """Map strict `criterion_idx` model output to canonical criteria.v2 items."""
    normalized_criteria = [str(name).strip() for name in criteria]
    if any(not name for name in normalized_criteria):
        raise RuntimeError("invalid_criterion_idx")

    mapped: dict[int, CriterionResult] = {}
    for item in lean_results:
        idx = item.criterion_idx
        if idx < 0 or idx >= len(normalized_criteria):
            raise RuntimeError("invalid_criterion_idx")
        if idx in mapped:
            raise RuntimeError("invalid_criterion_idx")
        score = max(0, min(int(item.score), 10))
        explanation = str(item.explanation_md or "").strip() or default_explanation_md
        mapped[idx] = CriterionResult(
            criterion=normalized_criteria[idx],
            max_score=10,
            score=score,
            explanation_md=explanation,
        )

    if len(mapped) != len(normalized_criteria):
        raise RuntimeError("invalid_criterion_idx")

    return [mapped[idx] for idx in range(len(normalized_criteria))]


def _derive_overall_score(*, criteria_results: list[CriterionResult]) -> int:
    """Derive an overall 0..5 score from per-criterion results.

    Why:
        The UI derives aggregate scores from per-criterion results. We keep an
        overall `analysis_json.score` field for backwards compatibility, but we
        do not require the model to produce it.

    Rules:
        - Normalise each criterion to a 0..10 scale using `max_score` (default 10).
        - Average across all criteria.
        - Map 0..10 -> 0..5 by dividing by 2 and rounding half-up.
    """
    if not criteria_results:
        return 0
    normalized: list[float] = []
    for item in criteria_results:
        try:
            max_score = int(item.max_score)
        except Exception:
            max_score = 10
        if max_score <= 0:
            max_score = 10
        try:
            score = int(item.score)
        except Exception:
            score = 0
        score = max(0, min(score, max_score))
        normalized.append(score / float(max_score) * 10.0)
    if not normalized:
        return 0
    avg_0_to_10 = sum(normalized) / len(normalized)
    # Round half-up to an integer score on a 0..5 scale.
    derived = int(avg_0_to_10 / 2.0 + 0.5)
    return max(0, min(derived, 5))


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
    criteria_list = list(criteria)
    out = predict(
        student_text_md=text_md,
        criteria=criteria_list,
        teacher_instructions_md=teacher_instructions_md,
        teacher_context_md=teacher_context_md,
    )
    lean_results = _ensure_lean_criteria_results(getattr(out, "criteria_results", []))
    results = _map_lean_results_to_criteria(
        criteria=criteria_list,
        lean_results=lean_results,
        default_explanation_md="Kein Beleg im Schülertext gefunden.",
    )
    score_int = _derive_overall_score(criteria_results=results)
    return CriteriaAnalysis(
        schema="criteria.v2",
        score=score_int,
        criteria_results=results,
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
    criteria_list = list(criteria)
    out = predict(
        student_image=img,
        criteria=criteria_list,
        teacher_instructions_md=teacher_instructions_md,
        teacher_context_md=teacher_context_md,
    )
    lean_results = _ensure_lean_criteria_results(getattr(out, "criteria_results", []))
    results = _map_lean_results_to_criteria(
        criteria=criteria_list,
        lean_results=lean_results,
        default_explanation_md="Kein Beleg im visuellen Inhalt gefunden.",
    )
    score_int = _derive_overall_score(criteria_results=results)
    return CriteriaAnalysis(
        schema="criteria.v2",
        score=score_int,
        criteria_results=results,
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
