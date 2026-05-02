"""
DSPy visual feedback program (image/PDF → analysis → synthesis).

Intent:
    Visual tasks are evaluated directly from the uploaded visual input
    (image/PDF) via a vision-capable model. The pipeline mirrors the text
    pipeline:
      1) structured rubric analysis (`criteria.v2`)
      2) formative prose feedback (Markdown)

Design principles:
    - Fail-fast: no deterministic fallback output; errors bubble to the worker.
    - Contract-first: normalize analysis to `criteria.v2` and validate the
      feedback formatting expected by the plan document.
"""

from __future__ import annotations

from contextlib import nullcontext
import logging
from typing import Any, Sequence

from backend.learning.adapters.dspy import json_observability
from backend.learning.adapters.dspy import programs as dspy_programs
from backend.learning.adapters.dspy.usage import capture_dspy_usage
from backend.learning.adapters.dspy.types import CriteriaAnalysis
from backend.learning.adapters.ports import FeedbackResult, TokenUsageEvent

LOG = logging.getLogger(__name__)

_REQUIRED_FEEDBACK_HEADINGS = (
    "**Das ist dir gut gelungen:**",
    "**Das kannst du besser:**",
)

_REPAIRABLE_ANALYSIS_ERRORS = {"invalid_analysis_json", "invalid_criterion_idx"}


def _validate_feedback_md(feedback_md: str) -> str:
    text = (feedback_md or "").strip()
    if not text:
        raise RuntimeError("empty_feedback_md")
    for heading in _REQUIRED_FEEDBACK_HEADINGS:
        if heading not in text:
            raise RuntimeError("invalid_feedback_format")
    return text


def _validate_feedback_md_with_usage(feedback_md: str, usage_events: list[TokenUsageEvent]) -> str:
    """Validate feedback and preserve already captured provider usage on errors."""
    try:
        return _validate_feedback_md(feedback_md)
    except RuntimeError as exc:
        if usage_events:
            setattr(exc, "usage_events", list(usage_events))
        raise


def _normalize_v2(*, raw: dict[str, Any], criteria: Sequence[str]) -> dict[str, Any]:
    items = raw.get("criteria_results") or raw.get("criteria") or []
    model_items: list[dict[str, Any]] = [it for it in items if isinstance(it, dict)] if isinstance(items, list) else []

    selected: dict[str, dict[str, Any]] = {}
    used_indices: set[int] = set()
    for expected in criteria:
        for idx, item in enumerate(model_items):
            if idx in used_indices:
                continue
            name = str(item.get("criterion") or item.get("name") or "").strip()
            if name == expected:
                selected[expected] = item
                used_indices.add(idx)
                break
    for expected in criteria:
        if expected in selected:
            continue
        for idx, item in enumerate(model_items):
            if idx in used_indices:
                continue
            selected[expected] = item
            used_indices.add(idx)
            break

    norm_items: list[dict[str, Any]] = []
    for name in criteria:
        key = str(name)
        item = selected.get(key)
        if not isinstance(item, dict):
            norm_items.append(
                {
                    "criterion": key,
                    "max_score": 10,
                    "score": 0,
                    "explanation_md": "Kein Beleg im visuellen Inhalt gefunden.",
                }
            )
            continue
        try:
            max_score = int(item.get("max_score", item.get("max", 10)))
        except Exception:
            max_score = 10
        if max_score <= 0:
            max_score = 10
        try:
            score = int(item.get("score", 0))
        except Exception:
            score = 0
        if score < 0:
            score = 0
        if score > max_score:
            score = max_score
        explanation = (
            str(item.get("explanation_md") or item.get("explanation") or "").strip()
            or "Kein Beleg im visuellen Inhalt gefunden."
        )
        norm_items.append({"criterion": key, "max_score": max_score, "score": score, "explanation_md": explanation})

    try:
        overall = int(raw.get("score", 0))
    except Exception:
        overall = 0
    if overall < 0:
        overall = 0
    if overall > 5:
        overall = 5

    return {"schema": "criteria.v2", "score": overall, "criteria_results": norm_items}


def _log_stage_metadata(*, stage: str, parse_status: str | None = None) -> None:
    """Write internal DSPy observability logs without leaking prompt content."""
    metadata = json_observability.pop_last_call_metadata()
    if not metadata:
        return
    LOG.info(
        "learning.feedback.dspy_stage_completed stage=%s model=%s provider=%s response_format_mode=%s "
        "response_format_requested=%s reasoning_effort=%s parse_status=%s",
        stage,
        metadata.get("model") or "",
        metadata.get("provider") or "",
        metadata.get("response_format_mode") or "",
        metadata.get("response_format_requested") or "",
        metadata.get("reasoning_effort") or "",
        parse_status or "",
    )
    if metadata.get("response_format_mode") == "json_object_fallback":
        LOG.warning(
            "learning.feedback.dspy_response_format_fallback stage=%s model=%s provider=%s reasoning_effort=%s",
            stage,
            metadata.get("model") or "",
            metadata.get("provider") or "",
            metadata.get("reasoning_effort") or "",
        )


def _dspy_context_for_lm(lm, *, stage: str):  # type: ignore[no-untyped-def]
    """Use a dedicated DSPy context only when a stage-specific LM is provided."""
    json_observability.clear_last_call_metadata()
    if lm is None:
        return nullcontext()
    import dspy  # type: ignore

    return dspy.context(  # type: ignore[attr-defined]
        lm=lm,
        adapter=json_observability.build_json_adapter(stage=stage),
        disable_history=True,
    )


def _lm_model(lm) -> str:  # type: ignore[no-untyped-def]
    return str(getattr(lm, "model", None) or "unknown")


def _run_analysis_with_repair(
    *,
    image_data_uri: str,
    criteria: Sequence[str],
    teacher_instructions_md: str | None,
    teacher_context_md: str | None,
    analysis_lm=None,  # type: ignore[no-untyped-def]
) -> tuple[CriteriaAnalysis | dict[str, Any], str, list[TokenUsageEvent]]:
    """Run visual analysis once and attempt exactly one repair on format errors."""
    events: list[TokenUsageEvent] = []
    try:
        with _dspy_context_for_lm(analysis_lm, stage="visual_analysis"):
            analysis, captured = capture_dspy_usage(
                lambda: dspy_programs.run_structured_visual_analysis(
                    image_data_uri=image_data_uri,
                    criteria=criteria,
                    teacher_instructions_md=teacher_instructions_md,
                    teacher_context_md=teacher_context_md,
                ),
                model=_lm_model(analysis_lm),
                stage="analysis",
                modality="visual",
                call_kind="primary",
            )
            events.extend(captured)
        _log_stage_metadata(stage="visual_analysis", parse_status="parsed_structured")
        return (analysis, "parsed_structured", events)
    except RuntimeError as exc:
        events.extend(list(getattr(exc, "usage_events", []) or []))
        reason = str(exc or "").strip().lower()
        if reason not in _REPAIRABLE_ANALYSIS_ERRORS:
            raise
        with _dspy_context_for_lm(analysis_lm, stage="visual_analysis"):
            analysis, captured = capture_dspy_usage(
                lambda: dspy_programs.run_structured_visual_analysis_repair(
                    image_data_uri=image_data_uri,
                    criteria=criteria,
                    repair_reason=reason,
                    teacher_instructions_md=teacher_instructions_md,
                    teacher_context_md=teacher_context_md,
                ),
                model=_lm_model(analysis_lm),
                stage="analysis",
                modality="visual",
                call_kind="repair",
            )
            events.extend(captured)
        _log_stage_metadata(stage="visual_analysis", parse_status="repaired_structured")
        return analysis, "repaired_structured", events


def analyze_visual_feedback(
    *,
    image_data_uri: str,
    criteria: Sequence[str],
    teacher_instructions_md: str | None = None,
    teacher_context_md: str | None = None,
    analysis_lm=None,  # type: ignore[no-untyped-def]
    synthesis_lm=None,  # type: ignore[no-untyped-def]
) -> FeedbackResult:
    """Run the Visual DSPy pipeline and return criteria.v2 analysis + feedback."""
    try:  # pragma: no cover - import is controlled by unit tests
        import dspy  # type: ignore

        _ = getattr(dspy, "__version__", None)
    except Exception:
        raise ImportError("dspy is not available")

    crit = [str(c).strip() for c in (criteria or []) if str(c).strip()]
    usage_events: list[TokenUsageEvent] = []
    if not crit:
        with _dspy_context_for_lm(synthesis_lm, stage="visual_synthesis"):
            feedback_md, captured = capture_dspy_usage(
                lambda: dspy_programs.run_visual_feedback_no_criteria(
                    image_data_uri=image_data_uri,
                    teacher_instructions_md=teacher_instructions_md,
                    teacher_context_md=teacher_context_md,
                ),
                model=_lm_model(synthesis_lm),
                stage="feedback",
                modality="visual",
                call_kind="no_criteria",
            )
            usage_events.extend(captured)
        _log_stage_metadata(stage="visual_synthesis", parse_status="skipped")
        return FeedbackResult(
            feedback_md=_validate_feedback_md_with_usage(feedback_md, usage_events),
            analysis_json={},
            parse_status="skipped",
            usage_events=usage_events,
        )

    analysis, parse_status, captured = _run_analysis_with_repair(
        image_data_uri=image_data_uri,
        criteria=crit,
        teacher_instructions_md=teacher_instructions_md,
        teacher_context_md=teacher_context_md,
        analysis_lm=analysis_lm,
    )
    usage_events.extend(captured)
    raw = analysis.to_dict() if isinstance(analysis, CriteriaAnalysis) else analysis
    if not isinstance(raw, dict):
        raise RuntimeError("invalid_analysis_json")
    analysis_json = _normalize_v2(raw=raw, criteria=crit)

    with _dspy_context_for_lm(synthesis_lm, stage="visual_synthesis"):
        feedback_md, captured = capture_dspy_usage(
            lambda: dspy_programs.run_structured_visual_feedback(
                image_data_uri=image_data_uri,
                criteria=crit,
                analysis_json=analysis_json,
                teacher_instructions_md=teacher_instructions_md,
                teacher_context_md=teacher_context_md,
            ),
            model=_lm_model(synthesis_lm),
            stage="feedback",
            modality="visual",
            call_kind="primary",
        )
        usage_events.extend(captured)
    _log_stage_metadata(stage="visual_synthesis")

    return FeedbackResult(
        feedback_md=_validate_feedback_md_with_usage(feedback_md, usage_events),
        analysis_json=analysis_json,
        parse_status=parse_status,
        usage_events=usage_events,
    )
