"""
DSPy visual feedback program (image → analysis → feedback).

Intent:
    Provide the DSPy-only pipeline for `Task.kind="visual"` where both
    - the criteria-based analysis and
    - the formative feedback
    are produced from a visual input (image/PDF) instead of OCR text.

Design notes:
    - The worker (or adapter) provides `image_data_uri` (base64) to avoid
      external downloads and keep the pipeline DSGVO-friendly by default.
    - The program uses the structured DSPy runner functions in
      `backend.learning.adapters.dspy.programs`.
    - Output is normalized to the existing `criteria.v2` JSON schema.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Sequence

from backend.learning.adapters.dspy import programs as dspy_programs
from backend.learning.adapters.dspy.types import CriteriaAnalysis
from backend.learning.adapters.ports import FeedbackResult


logger = logging.getLogger(__name__)

_TRUTHY = {"1", "true", "yes", "on"}


def _truthy_env(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUTHY


def _json_adapter_enabled() -> bool:
    return _truthy_env("LEARNING_DSPY_JSON_ADAPTER", default=True)


def _ensure_ollama_host_env() -> str | None:
    """Propagate OLLAMA_BASE_URL into env vars that LiteLLM/DSPy might use."""
    base_url = (os.getenv("OLLAMA_BASE_URL") or "").strip()
    if not base_url:
        return None
    if not (os.getenv("OLLAMA_HOST") or "").strip():
        os.environ["OLLAMA_HOST"] = base_url
    if not (os.getenv("OLLAMA_API_BASE") or "").strip():
        os.environ["OLLAMA_API_BASE"] = base_url
    return base_url


def _default_feedback_md() -> str:
    return "Kurze, konstruktive Rückmeldung basierend auf der visuellen Analyse."


def _normalize_v2(*, raw: dict[str, Any], criteria: Sequence[str]) -> dict[str, Any]:
    """Normalize a criteria.v2-ish dict to our canonical shape and ordering."""
    by_name: dict[str, dict[str, Any]] = {}
    items = raw.get("criteria_results", []) if isinstance(raw, dict) else []
    if isinstance(items, list):
        for it in items:
            if not isinstance(it, dict):
                continue
            name = str(it.get("criterion") or "").strip()
            if not name:
                continue
            by_name[name] = it

    norm_items: list[dict[str, Any]] = []
    for name in criteria:
        key = str(name)
        it = by_name.get(key)
        if not isinstance(it, dict):
            norm_items.append(
                {"criterion": key, "max_score": 10, "score": 0, "explanation_md": "Kein Beleg im visuellen Inhalt gefunden."}
            )
            continue
        try:
            max_score = int(it.get("max_score", 10))
        except Exception:
            max_score = 10
        if max_score <= 0:
            max_score = 10
        try:
            score = int(it.get("score", 0))
        except Exception:
            score = 0
        if score < 0:
            score = 0
        if score > max_score:
            score = max_score
        expl = str(it.get("explanation_md") or it.get("explanation") or "").strip() or "Kein Beleg im visuellen Inhalt gefunden."
        norm_items.append({"criterion": key, "max_score": max_score, "score": score, "explanation_md": expl})

    try:
        overall = int(raw.get("score", 0))
    except Exception:
        overall = 0
    if overall < 0:
        overall = 0
    if overall > 5:
        overall = 5

    return {"schema": "criteria.v2", "score": overall, "criteria_results": norm_items}


def analyze_visual_feedback(
    *,
    image_data_uri: str,
    criteria: Sequence[str],
    teacher_instructions_md: str | None = None,
    solution_hints_md: str | None = None,
) -> FeedbackResult:
    """Run the Visual DSPy pipeline and return criteria.v2 analysis + feedback."""
    try:  # pragma: no cover - presence is asserted in unit tests
        import dspy  # type: ignore
        _ = getattr(dspy, "__version__", None)
    except Exception:
        raise ImportError("dspy is not available")

    crit = [str(c) for c in (criteria or []) if str(c).strip()]
    if not crit:
        # Keep behaviour consistent with text pipeline: allow tasks without criteria.
        return FeedbackResult(feedback_md=_default_feedback_md(), analysis_json={}, parse_status="skipped")

    # Configure DSPy (LiteLLM) to use a vision-capable model for visual tasks.
    # Default precedence: AI_VISUAL_MODEL → AI_VISION_MODEL.
    model_name = (os.getenv("AI_VISUAL_MODEL") or "").strip() or (os.getenv("AI_VISION_MODEL") or "").strip()
    try:  # pragma: no cover - configuration is integration-tested elsewhere
        if model_name and hasattr(dspy, "LM"):
            api_base = _ensure_ollama_host_env()
            from backend.learning.adapters.dspy import helpers as dspy_helpers

            think_level = os.getenv("AI_THINK_LEVEL")
            lm_kwargs = dspy_helpers.build_lm_kwargs(
                model_name=model_name,
                api_base=api_base,
                think_level=think_level,
            )
            lm = dspy.LM(f"ollama/{model_name}", **lm_kwargs)  # type: ignore[attr-defined]
            adapter_cls = getattr(dspy, "JSONAdapter", None) if _json_adapter_enabled() else None
            if adapter_cls is not None:
                dspy.configure(lm=lm, adapter=adapter_cls())  # type: ignore[misc]
            else:
                dspy.configure(lm=lm)
    except Exception:
        # Keep the program robust: if configuration fails, still attempt to run.
        pass

    parse_status = "parsed_structured"
    try:
        analysis = dspy_programs.run_structured_visual_analysis(
            image_data_uri=image_data_uri,
            criteria=crit,
            teacher_instructions_md=teacher_instructions_md,
            solution_hints_md=solution_hints_md,
        )
        analysis_dict = analysis if isinstance(analysis, dict) else analysis.to_dict()
        analysis_json = _normalize_v2(raw=analysis_dict, criteria=crit)
    except Exception as exc:
        logger.warning("learning.visual_feedback.analysis_failed reason=%s", exc.__class__.__name__)
        analysis_json = {"schema": "criteria.v2", "score": 0, "criteria_results": []}
        parse_status = "analysis_fallback"

    feedback_md: str | None = None
    try:
        feedback_md = dspy_programs.run_structured_visual_feedback(
            image_data_uri=image_data_uri,
            criteria=crit,
            analysis_json=CriteriaAnalysis.from_dict(analysis_json).to_dict(),
            teacher_instructions_md=teacher_instructions_md,
        )
    except Exception as exc:
        logger.warning("learning.visual_feedback.feedback_failed reason=%s", exc.__class__.__name__)
        feedback_md = None

    feedback_out = (feedback_md or "").strip() or _default_feedback_md()
    if feedback_md is None:
        parse_status = "analysis_feedback_fallback" if parse_status != "parsed_structured" else "feedback_fallback"

    return FeedbackResult(feedback_md=feedback_out, analysis_json=analysis_json, parse_status=parse_status)

