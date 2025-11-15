"""DSPy program scaffolding for learning feedback (analysis → synthesis)."""

from __future__ import annotations

from typing import Any, Callable, Sequence

from backend.learning.adapters.dspy.signatures import (
    FeedbackAnalysisSignature,
    FeedbackSynthesisSignature,
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
    solution_hints_md: str | None = None,
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
        solution_hints_md=solution_hints_md,
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
    )
    val = getattr(out, "feedback_md", None)
    if isinstance(val, str) and val.strip() and val.strip().lower() != "none":
        return val
    # If the model omitted the field, synthesize a minimal prose from the analysis payload
    # (stay within DSPy path; no backend fallback here).
    items = payload.get("criteria_results", []) if isinstance(payload, dict) else []
    positives = [
        f"{i.get('criterion', 'Kriterium')}: {i.get('score', 0)}/{i.get('max_score', 10)}"
        for i in items
        if int(i.get("score", 0)) >= int(i.get("max_score", 10)) // 2
    ]
    improves = [
        f"{i.get('criterion', 'Kriterium')}"
        for i in items
        if int(i.get("score", 0)) < int(i.get("max_score", 10)) // 2
    ]
    parts = []
    if positives:
        parts.append("Stärken: " + ", ".join(positives) + ".")
    if improves:
        parts.append("Hinweise: gezielt ausbauen bei " + ", ".join(improves) + ".")
    return " ".join(parts) or "Kurze, konstruktive Rückmeldung basierend auf der Analyse."


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
        solution_hints_md: str | None = None,
    ) -> str:
        import inspect as _inspect
        kwargs = {"text_md": text_md, "criteria": criteria}
        try:
            sig = _inspect.signature(self._runner)
            if "teacher_instructions_md" in sig.parameters:
                kwargs["teacher_instructions_md"] = teacher_instructions_md
            if "solution_hints_md" in sig.parameters:
                kwargs["solution_hints_md"] = solution_hints_md
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
