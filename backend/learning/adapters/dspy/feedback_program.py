"""
DSPy feedback program (minimal, deterministic scaffold).

Intent:
    Provide a tiny, dependency-light wrapper that is called by the local
    Feedback adapter when `dspy` is importable. The goal is to make the
    decision path explicit and future‑proof without pulling in real model
    definitions here.

Design:
    - Keep logic deterministic for tests and education (KISS).
    - Accept `text_md` and a list of `criteria` and build a `criteria.v2`
      analysis structure plus a short Markdown feedback.
    - Importing `dspy` is intentionally shallow; tests monkeypatch a fake
      `dspy` module to assert this branch is taken without calling Ollama.

Security:
    - Do not log or return raw student text beyond structured output.
"""

from __future__ import annotations

import json
import os
import logging
import re
from typing import Any, Dict, Sequence

from backend.learning.adapters.dspy import programs as dspy_programs
from backend.learning.adapters.dspy.signatures import (  # noqa: F401
    FeedbackAnalysisSignature,
    FeedbackSynthesisSignature,
)
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
    """Feature flag for JSONAdapter (default on; set env to 'false' to disable)."""
    return _truthy_env("LEARNING_DSPY_JSON_ADAPTER", default=True)


def _ensure_ollama_host_env() -> str | None:
    """
    DSPy (LiteLLM) expects api_base and/or OLLAMA_HOST. Propagate OLLAMA_BASE_URL.

    This mirrors docker-compose where only the base URL is configured. By
    setting the host lazily we retain compatibility with any manual overrides.
    """
    base_url = (os.getenv("OLLAMA_BASE_URL") or "").strip()
    if not base_url:
        return None
    if not (os.getenv("OLLAMA_HOST") or "").strip():
        os.environ["OLLAMA_HOST"] = base_url
    if not (os.getenv("OLLAMA_API_BASE") or "").strip():
        os.environ["OLLAMA_API_BASE"] = base_url
    return base_url


def _sanitize_text(text_md: str) -> str:
    """Return student text verbatim; truncation happens in prompt builders."""
    return text_md


def _clip(text: str | None, *, max_chars: int) -> str:
    """Bound prompt parts to a safe size to avoid LM server errors (e.g., 500).

    Rationale:
        Long prompts (task instructions + full analysis JSON + student text)
        can exceed the model/context capacity and trigger 500s from local LM
        servers. We conservatively clamp each part to keep prompts small and
        robust for classroom use without changing semantics.
    """
    if not text:
        return ""
    s = str(text)
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 10] + "\n[truncated]"


def _build_analysis_prompt(
    *, text_md: str, criteria: Sequence[str], teacher_instructions_md: str | None = None, solution_hints_md: str | None = None
) -> str:
    """Build a simple, privacy‑aware instruction and output contract.

    Emphasises:
    - No leakage of student text in the response.
    - Output must be JSON following criteria.v2 schema (loosely described).
    - Criteria names are included so the model can align explanations.
    """
    crit_lines = "\n".join(f"- {str(c)}" for c in criteria)
    # Conservative per‑section limits keep the total prompt size manageable.
    instr = _clip(teacher_instructions_md, max_chars=4000)
    hints = _clip(solution_hints_md, max_chars=2000)
    text = _clip(_sanitize_text(text_md), max_chars=6000)

    parts = [
        "Rolle: Lehrkraft. Führe eine Kriterien-Analyse durch.",
        "Datenschutz: Gib nur Analysewerte und kurze Begründungen aus.",
        "Ausgabe: Striktes JSON im Schema 'criteria.v2' mit 'criteria_results' (Objekte mit criterion, max_score=10, score 0..10, explanation_md).",
        "Kriterien (Reihenfolge beibehalten):\n" + crit_lines,
    ]
    if instr:
        parts.append("Aufgabenstellung (nur zur Analyse):\n" + instr)
    if hints:
        parts.append("Lösungshinweise (nur zur Analyse; nicht offenlegen):\n" + hints)
    parts.append("Schülertext (wörtlich):\n" + text)
    parts.append("Gib ausschließlich das JSON zurück, keine Prosa.")
    return "\n".join(parts)


def _build_feedback_prompt(
    *,
    text_md: str,
    criteria: Sequence[str],
    analysis_json: Dict[str, Any],
    teacher_instructions_md: str | None = None,
) -> str:
    """Prompt instructing the LM to turn structured analysis into concise prose feedback.

    Note:
        Do not embed the full analysis JSON verbatim; large payloads increased
        failure rates on local LM backends. We include a concise criteria
        summary and clamp all text sections.
    """
    crit_summary = "\n".join(
        f"- {item['criterion']}: {item['score']}/{item['max_score']}"
        for item in analysis_json.get("criteria_results", [])
    )
    instr = _clip(teacher_instructions_md, max_chars=2000)
    text = _clip(_sanitize_text(text_md), max_chars=4000)

    parts = [
        "Rolle: Lehrkraft. Formuliere eine kurze, gut lesbare Rückmeldung im Fließtext, basierend auf der Analyse.",
        "Regeln:",
        "1. Nenne kurz, was gut gelungen ist, und was beim nächsten Mal verbessert werden kann.",
        "2. Schreibe verständliche, zusammenhängende Sätze (keine Listen/Bullets).",
        "3. Wiederhole den Schülertext nicht vollständig; beziehe dich auf die analysierten Kriterien.",
        "Analyse-Zusammenfassung:\n" + (crit_summary or "- No criteria provided."),
    ]
    if instr:
        parts.append("Aufgabenstellung (Kontext):\n" + instr)
    parts.append("Schülertext (wörtlich):\n" + text)
    parts.append("Gib ausschließlich den Rückmeldungstext in Markdown (Fließtext) zurück.")
    return "\n".join(parts)


def _sanitize_sample(raw: str) -> str:
    sample = " ".join(raw.split())
    if len(sample) > 160:
        return sample[:157] + "..."
    return sample


def _log_parse_failure(*, reason: str, raw: str) -> None:
    logger.warning(
        "learning.feedback.dspy_parse_failed reason=%s sample=%s",
        reason,
        _sanitize_sample(raw),
    )


def _parse_to_v2(raw: str, *, criteria: Sequence[str]) -> tuple[Dict[str, Any] | None, str | None]:
    """Parse model output to criteria.v2; return None if irreparably malformed.

    Accepts minor field variations and normalizes:
    - overall `score` clamped to [0,5]
    - items under `criteria_results` or `criteria`
      with keys `criterion|name`, `max_score|max`, `explanation_md|explanation`
    - scores clamped to [0,max_score]
    - explanations kept verbatim; empty ones get a neutral default
    - ensure each expected criterion appears (fill with defaults if missing)
    Returns:
        Tuple of (analysis_json | None, feedback_md | None).
    """
    cleaned = _unwrap_code_block(raw)
    try:
        obj = json.loads(cleaned)
    except Exception:
        _log_parse_failure(reason="json_decode", raw=raw)
        return None, None

    feedback_val = obj.get("feedback_md") or obj.get("feedback") or obj.get("feedback_markdown")
    feedback_md = feedback_val.strip() if isinstance(feedback_val, str) and feedback_val.strip() else None

    # Extract candidate items list with field variants
    items_raw = obj.get("criteria_results") or obj.get("criteria") or []
    by_name: Dict[str, Dict[str, Any]] = {}
    ordered_items: list[Dict[str, Any]] = []
    for it in items_raw:
        name = it.get("criterion") or it.get("name")
        if not name:
            continue
        max_s = it.get("max_score") if it.get("max_score") is not None else it.get("max")
        try:
            max_i = int(max_s) if max_s is not None else 10
        except Exception:
            max_i = 10
        sc = it.get("score")
        try:
            sc_i = int(sc)
        except Exception:
            try:
                sc_i = int(float(sc))  # cope with "4.0"
            except Exception:
                sc_i = 0
        # clamp
        if sc_i < 0:
            sc_i = 0
        if sc_i > max_i:
            sc_i = max_i
        expl = (it.get("explanation_md") or it.get("explanation") or "").strip()
        # Neutral fallback avoids repeating the criterion title in the body text.
        normalized_item = {
            "criterion": str(name),
            "max_score": max_i,
            "score": sc_i,
            "explanation_md": str(expl) if expl else "Kein Beleg im Schülertext gefunden.",
        }
        by_name[str(name)] = normalized_item
        ordered_items.append(dict(normalized_item))

    # Build normalized list following requested ordering and fill missing
    norm_items: list[Dict[str, Any]] = []
    expected_count = len(list(criteria))
    items_raw_count = len(ordered_items)  # number of items emitted by the model
    for name in criteria:
        key = str(name)
        if key in by_name:
            norm_items.append(by_name[key])
            continue
        # Alignment by order ONLY when the model returned at least as many items
        # as expected (pure renaming case). Do not consume items if the model
        # produced fewer entries than required; synthesize defaults instead.
        if ordered_items and items_raw_count >= expected_count:
            item = ordered_items.pop(0)
            item["criterion"] = key
            norm_items.append(item)
            continue
        # Otherwise, fill deterministically
        norm_items.append(
            {
                "criterion": key,
                "max_score": 10,
                "score": 0,
                "explanation_md": "Kein Beleg im Schülertext gefunden.",
            }
        )

    # Overall score: prefer provided, else compute average normalized → [0,5]
    overall = obj.get("score")
    try:
        overall_i = int(overall)
    except Exception:
        try:
            overall_i = int(float(overall))
        except Exception:
            # derive from items
            if norm_items:
                ratio = sum((i["score"] / max(1, i["max_score"])) for i in norm_items) / len(norm_items)
                overall_i = max(0, min(5, round(ratio * 5)))
            else:
                overall_i = 0
    if overall_i < 0:
        overall_i = 0
    if overall_i > 5:
        overall_i = 5

    return {"schema": "criteria.v2", "score": overall_i, "criteria_results": norm_items}, feedback_md


_CODE_FENCE_PATTERN = re.compile(r"```(?:[a-zA-Z0-9_-]+)?\s*(.*?)\s*```", re.DOTALL)


def _unwrap_code_block(raw: str) -> str:
    """Strip triple-backtick fences (```json ... ```) emitted by many LLMs."""
    stripped = raw.strip()
    match = _CODE_FENCE_PATTERN.search(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def _build_default_analysis(criteria: Sequence[str]) -> Dict[str, Any]:
    """Deterministic fallback analysis."""
    crit_items = [
        {
            "criterion": str(name),
            "max_score": 10,
            # No assumptions without evidence → start at 0
            "score": 0,
            # Keep fallback concise; the UI already shows the criterion title separately.
            "explanation_md": "Kein Beleg im Schülertext gefunden.",
        }
        for name in criteria
    ]
    # Overall derives to 0 when all items are 0
    return {"schema": "criteria.v2", "score": 0, "criteria_results": crit_items}


def _default_feedback_md() -> str:
    return (
        "**Rückmeldung**\n\n"
        "- Stärken: klar benannt.\n"
        "- Nächste Schritte: einzelne Kriterien gezielt verbessern."
    )


def _analysis_dict_to_payload(analysis_json: dict[str, Any]) -> CriteriaAnalysis:
    try:
        return CriteriaAnalysis.from_dict(analysis_json)
    except Exception:
        return CriteriaAnalysis(schema=str(analysis_json.get("schema", "criteria.v2")), score=int(analysis_json.get("score", 0)), criteria_results=[])


# Legacy hook shims used by integration tests; monkeypatched to drive deterministic output.
def _run_analysis_model(*, text_md: str, criteria, teacher_instructions_md=None, solution_hints_md=None):
    return _build_default_analysis(criteria)


def _run_feedback_model(*, text_md: str, criteria, analysis_json):
    return _default_feedback_md()


def analyze_feedback(
    *,
    text_md: str,
    criteria: Sequence[str],
    teacher_instructions_md: str | None = None,
    solution_hints_md: str | None = None,
) -> FeedbackResult:
    """Run the DSPy-only feedback pipeline and return criteria.v2 analysis + feedback.

    Why:
        This function is the single orchestration point for learning feedback
        when DSPy is available. It hides all LM details behind DSPy Signatures
        and Modules so that the local adapter stays simple and the behaviour is
        easy to test and explain in class.

    Parameters:
        text_md:
            Learner submission in Markdown. The raw text is only used inside
            DSPy calls and never logged or returned verbatim.
        criteria:
            Ordered list of criterion labels used for the rubric. Each entry
            becomes one item in the `criteria_results` array.
        teacher_instructions_md:
            Optional Markdown task description for context (e.g. assignment
            wording). It may influence analysis/feedback but must not be
            leaked into explanations.
        solution_hints_md:
            Optional teacher-only hints or sample solutions. They are passed
            as private context for analysis and must never be quoted back to
            students.

    Returns:
        FeedbackResult:
            - feedback_md: formative feedback in Markdown (prose, no lists).
            - analysis_json: JSON object in the `criteria.v2` schema.
            - parse_status: marker such as "parsed_structured" or
              "analysis_feedback_fallback" for observability.

    Necessary permissions:
        This function is invoked by the learning worker process under the
        configured DB role (e.g. gustav_worker). End-user authorisation and
        RLS checks happen upstream; the function must only operate on the
        already authorised submission data and must not leak student text
        through logs or telemetry.
    """
    # NOTE: Import dspy shallowly to select this program only when available.
    try:  # pragma: no cover - presence is tested from adapter, not here
        import dspy  # type: ignore
        _ = getattr(dspy, "__version__", None)  # touch to prove availability
    except Exception:
        # If import fails at this layer, let callers fall back to non-DSPy path.
        raise ImportError("dspy is not available")

    if not criteria:
        # No criteria configured for the task:
        # - we still want a short, encouraging feedback text
        # - there is no per-criterion analysis payload to persist
        # To keep the architecture uniform, we stay inside the DSPy path and
        # call the structured feedback helper with an empty analysis object.
        try:
            feedback_only = dspy_programs.run_structured_feedback(
                text_md=text_md,
                criteria=[],
                analysis_json=CriteriaAnalysis(schema="criteria.v2", score=0, criteria_results=[]),
                teacher_instructions_md=teacher_instructions_md,
            )
        except TimeoutError:
            raise
        except Exception as exc:
            logger.warning("learning.feedback.feedback_model_failed reason=%s", exc.__class__.__name__)
            feedback_only = _default_feedback_md()

        logger.info(
            "learning.feedback.dspy_pipeline_completed feedback_source=%s parse_status=%s criteria_count=%s",
            "no_criteria",
            "skipped",
            0,
        )
        return FeedbackResult(feedback_md=feedback_only, analysis_json={}, parse_status="skipped")

    # Try structured DSPy path first. If anything fails, fall back below.
    parse_status = "parsed"
    feedback_source = "synthesis"
    structured_failed = False
    try:
        # Best-effort DSPy configuration for local Ollama models; this is a
        # thin adapter over the environment variables used elsewhere in the
        # system (AI_FEEDBACK_MODEL, OLLAMA_BASE_URL).
        try:  # pragma: no cover - exercised indirectly in integration/E2E
            import dspy  # type: ignore
            model_name = (os.getenv("AI_FEEDBACK_MODEL") or "").strip()
            if model_name and hasattr(dspy, "LM"):
                api_base = _ensure_ollama_host_env()
                lm_kwargs = {"api_base": api_base} if api_base else {}
                lm = dspy.LM(f"ollama/{model_name}", **lm_kwargs)  # type: ignore[attr-defined]
                use_json_adapter = _json_adapter_enabled()
                adapter_cls = getattr(dspy, "JSONAdapter", None) if use_json_adapter else None
                if adapter_cls is not None:
                    dspy.configure(lm=lm, adapter=adapter_cls())  # type: ignore[misc]
                else:
                    # Default path keeps prompts simple and skips strict JSON enforcement.
                    dspy.configure(lm=lm)
        except Exception:
            pass
        structured_analysis = dspy_programs.run_structured_analysis(
            text_md=text_md,
            criteria=criteria,
            teacher_instructions_md=teacher_instructions_md,
            solution_hints_md=solution_hints_md,
        )
        if isinstance(structured_analysis, dict):
            structured_analysis = CriteriaAnalysis.from_dict(structured_analysis)
        structured_json = structured_analysis.to_dict()
        raw_structured = json.dumps(structured_json, ensure_ascii=False)
        analysis_json, embedded_feedback = _parse_to_v2(raw_structured, criteria=criteria)
        if analysis_json is None:
            analysis_json = _build_default_analysis(criteria)
            parse_status = "analysis_fallback"
        else:
            parse_status = "parsed_structured"
        analysis_payload = _analysis_dict_to_payload(analysis_json)

        feedback_md: str | None = None
        try:
            feedback_md = dspy_programs.run_structured_feedback(
                text_md=text_md,
                criteria=criteria,
                analysis_json=analysis_payload.to_dict(),
                teacher_instructions_md=teacher_instructions_md,
            )
        except Exception:
            feedback_md = None

        if not feedback_md or not feedback_md.strip():
            if embedded_feedback:
                feedback_md = embedded_feedback
                feedback_source = "analysis_embed"
            else:
                if parse_status == "parsed_structured":
                    parse_status = "feedback_fallback"
                else:
                    parse_status = "analysis_feedback_fallback"
                feedback_md = _default_feedback_md()
                feedback_source = "fallback"
        else:
            feedback_source = "feedback"

        logger.info(
            "learning.feedback.dspy_pipeline_completed feedback_source=%s parse_status=%s criteria_count=%s",
            feedback_source,
            parse_status,
            len(criteria),
        )
        return FeedbackResult(feedback_md=feedback_md, analysis_json=analysis_json, parse_status=parse_status)
    except TimeoutError:
        raise
    except Exception as exc:
        structured_failed = True
        logger.warning("learning.feedback.dspy_structured_failed reason=%s", exc.__class__.__name__)

    # Fallback: use legacy single-step runners (monkeypatch-friendly for tests)
    try:
        import inspect as _inspect

        kwargs = {"text_md": text_md, "criteria": criteria}
        try:
            sig = _inspect.signature(_run_analysis_model)
            if "teacher_instructions_md" in sig.parameters:
                kwargs["teacher_instructions_md"] = teacher_instructions_md
            if "solution_hints_md" in sig.parameters:
                kwargs["solution_hints_md"] = solution_hints_md
        except Exception:
            # Best effort; fall back to minimal kwargs
            pass

        raw_analysis = _run_analysis_model(**kwargs)
        if isinstance(raw_analysis, str):
            try:
                analysis_json = json.loads(raw_analysis)
            except Exception:
                analysis_json = _build_default_analysis(criteria)
        elif isinstance(raw_analysis, CriteriaAnalysis):
            analysis_json = raw_analysis.to_dict()
        elif isinstance(raw_analysis, dict):
            analysis_json = raw_analysis
        else:
            analysis_json = _build_default_analysis(criteria)
    except Exception as exc:
        logger.warning("learning.feedback.legacy_analysis_failed reason=%s", exc.__class__.__name__)
        analysis_json = _build_default_analysis(criteria)

    try:
        import inspect as _inspect

        fb_kwargs = {"text_md": text_md, "criteria": criteria, "analysis_json": analysis_json}
        try:
            sig = _inspect.signature(_run_feedback_model)
            if "teacher_instructions_md" in sig.parameters:
                fb_kwargs["teacher_instructions_md"] = teacher_instructions_md
        except Exception:
            pass

        feedback_md = _run_feedback_model(**fb_kwargs)
        if not isinstance(feedback_md, str) or not feedback_md.strip():
            raise RuntimeError("empty feedback from legacy LM")
        feedback_md = feedback_md.strip()
    except TimeoutError:
        logger.warning("learning.feedback.legacy_feedback_failed reason=timeout")
        # Escalate timeout so caller can retry or fall back to another adapter.
        raise
    except Exception as exc:
        logger.warning("learning.feedback.legacy_feedback_failed reason=%s", exc.__class__.__name__)
        # Signal failure to caller instead of returning a stub.
        raise RuntimeError("legacy_feedback_failed") from exc

    parse_status = "analysis_feedback_fallback" if structured_failed else "legacy"
    feedback_source = "legacy"
    logger.info(
        "learning.feedback.dspy_pipeline_completed feedback_source=%s parse_status=%s criteria_count=%s",
        feedback_source,
        parse_status,
        len(criteria),
    )
    return FeedbackResult(feedback_md=feedback_md, analysis_json=analysis_json, parse_status=parse_status)
