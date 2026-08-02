"""DSPy assessment program with typed separation of performance and context."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any, Sequence

import dspy  # type: ignore

from backend.learning.adapters.dspy.programs import (
    _derive_overall_score,
    _ensure_lean_criteria_results,
    _map_lean_results_to_criteria,
)
from backend.learning.adapters.ports import FeedbackResult


class DialogAssessmentSignature(dspy.Signature):  # type: ignore[attr-defined]
    """Bewerte ausschließlich die als Schülerleistung markierten Beiträge.

    `student_performance` enthält Schülernachrichten, dokumentierte
    Hilfestellungsmarker und optional die Abschlussantwort. Übernommene
    Satzanfänge sind Hilfen und kein eigenständiger Leistungsbeleg.
    `conversation_context` enthält ausschließlich KI-Nachrichten. Diese helfen
    beim Verständnis, dürfen aber niemals als Schülerleistung gewertet werden.
    Bei leerer Kriterienliste entsteht nur formative Rückmeldung.
    """

    student_performance: dict[str, Any] = dspy.InputField()
    conversation_context: dict[str, Any] = dspy.InputField()
    criteria: list[str] = dspy.InputField()
    task_instruction_md: str = dspy.InputField()
    criteria_results: list[Any] = dspy.OutputField()
    feedback_md: str = dspy.OutputField()


def analyze_dialog(
    *,
    student_performance: dict[str, Any],
    conversation_context: dict[str, Any],
    criteria: Sequence[str],
    instruction_md: str,
    lm=None,  # type: ignore[no-untyped-def]
) -> FeedbackResult:
    """Return criteria.v2 (when configured) plus formative feedback."""

    criteria_list = [str(value).strip() for value in criteria if str(value).strip()]
    scope = dspy.context(lm=lm, disable_history=True) if lm is not None else nullcontext()
    with scope:
        result = dspy.Predict(DialogAssessmentSignature)(
            student_performance=student_performance,
            conversation_context=conversation_context,
            criteria=criteria_list,
            task_instruction_md=instruction_md,
        )
    feedback_md = str(getattr(result, "feedback_md", "") or "").strip()
    if not feedback_md:
        raise RuntimeError("empty_feedback_md")
    if not criteria_list:
        return FeedbackResult(feedback_md=feedback_md, analysis_json={})
    lean = _ensure_lean_criteria_results(getattr(result, "criteria_results", []))
    mapped = _map_lean_results_to_criteria(
        criteria=criteria_list,
        lean_results=lean,
        default_explanation_md="Kein Beleg in der Schülerleistung gefunden.",
    )
    return FeedbackResult(
        feedback_md=feedback_md,
        analysis_json={
            "schema": "criteria.v2",
            "score": _derive_overall_score(criteria_results=mapped),
            "criteria_results": [item.to_dict() for item in mapped],
        },
    )
