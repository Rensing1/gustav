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


def _lm_call(*, prompt: str, timeout: int) -> str:
    """Invoke the configured Ollama model (monkeypatch friendly for tests)."""
    base_url = (os.getenv("OLLAMA_BASE_URL") or "").strip()
    model_name = (os.getenv("AI_FEEDBACK_MODEL") or "").strip()
    if not base_url:
        raise RuntimeError("OLLAMA_BASE_URL must be set for DSPy feedback")
    if not model_name:
        raise RuntimeError("AI_FEEDBACK_MODEL must be set for DSPy feedback")

    try:
        import ollama  # type: ignore
    except Exception as exc:  # pragma: no cover - exercised via adapter tests
        raise RuntimeError(f"ollama client unavailable: {exc}") from exc

    client = ollama.Client(base_url)
    # Use raw mode to bypass model templates on the server, avoiding template errors
    # like "function 'currentDate' not defined" and to keep prompts under our control.
    raw = client.generate(
        model=model_name,
        prompt=prompt,
        options={
            "raw": True,
            # Override any model Modelfile templates to avoid server-side template parsing
            # errors (e.g., unknown functions) and keep prompt under our control.
            "template": "{{ .Prompt }}",
        },
    )
    if isinstance(raw, dict):
        response = raw.get("response") or raw.get("message")
        if isinstance(response, str):
            return response
        return json.dumps(raw)
    if isinstance(raw, str):
        return raw
    return json.dumps(raw)


def _run_model(
    *, text_md: str, criteria: Sequence[str], teacher_instructions_md: str | None = None, solution_hints_md: str | None = None
) -> str:
    """Run the (mockable) LM call using a structured prompt.

    Tests may monkeypatch this function directly or the `_lm_call` shim to
    intercept prompt content and return tailored outputs.
    """
    prompt = _build_analysis_prompt(
        text_md=text_md,
        criteria=criteria,
        teacher_instructions_md=teacher_instructions_md,
        solution_hints_md=solution_hints_md,
    )
    timeout = int(os.getenv("AI_TIMEOUT_FEEDBACK", "30"))
    return _lm_call(prompt=prompt, timeout=timeout)


def _run_analysis_model(
    *, text_md: str, criteria: Sequence[str], teacher_instructions_md: str | None = None, solution_hints_md: str | None = None
) -> str:
    """Indirection to keep legacy `_run_model` patchable in tests."""
    return _run_model(
        text_md=text_md,
        criteria=criteria,
        teacher_instructions_md=teacher_instructions_md,
        solution_hints_md=solution_hints_md,
    )


def _run_feedback_model(
    *,
    text_md: str,
    criteria: Sequence[str],
    analysis_json: Dict[str, Any],
    teacher_instructions_md: str | None = None,
) -> str:
    """Execute the feedback synthesis LM call."""
    prompt = _build_feedback_prompt(
        text_md=text_md,
        criteria=criteria,
        analysis_json=analysis_json,
        teacher_instructions_md=teacher_instructions_md,
    )
    timeout = int(os.getenv("AI_TIMEOUT_FEEDBACK", "30"))
    return _lm_call(prompt=prompt, timeout=timeout)


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
        expl = it.get("explanation_md") or it.get("explanation") or ""
        # ensure the criterion name appears for clarity
        if str(name) not in str(expl):
            expl = f"{expl} (Bezug: {name})".strip()
        normalized_item = {
            "criterion": str(name),
            "max_score": max_i,
            "score": sc_i,
            "explanation_md": str(expl) if expl else f"Bezug zum Kriterium „{name}“",
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
                "explanation_md": f"Bezug zum Kriterium „{key}“",
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
            "explanation_md": f"Bezug zum Kriterium „{str(name)}“",
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


def analyze_feedback(
    *,
    text_md: str,
    criteria: Sequence[str],
    teacher_instructions_md: str | None = None,
    solution_hints_md: str | None = None,
) -> FeedbackResult:
    """Produce minimal Markdown feedback and criteria.v2 analysis via DSPy path.

    Why:
        The local adapter prefers a DSPy‑based flow when the module is
        importable. This function centralises the behavior, keeping the
        adapter narrow and easy to test.

    Parameters:
        text_md: Learner submission as Markdown (not logged here).
        criteria: Ordered list of criteria names.

    Returns:
        FeedbackResult with Markdown feedback and `criteria.v2` analysis.

    Notes:
        - The DSPy JSONAdapter is enabled by default; set
          `LEARNING_DSPY_JSON_ADAPTER=false` locally if a model cannot emit
          strict JSON for the structured signatures.
        - `OLLAMA_BASE_URL` must point to the reachable Ollama service; this
          function propagates it to `OLLAMA_HOST` for LiteLLM/DSPy.

    Permissions:
        Invoked by the learning worker (gustav_worker role). End-user context
        is already authorized upstream; this function must not leak student text.
    """
    # NOTE: Import dspy shallowly to select this program only when available.
    try:  # pragma: no cover - presence is tested from adapter, not here
        import dspy  # type: ignore
        _ = getattr(dspy, "__version__", None)  # touch to prove availability
    except Exception:
        # If import fails at this layer, let callers fall back to non-DSPy path.
        raise ImportError("dspy is not available")

    api_base = _ensure_ollama_host_env()

    if not criteria:
        # No criteria: produce feedback prose without an analysis payload.
        try:
            feedback_only = _run_feedback_model(
                text_md=text_md,
                criteria=[],
                analysis_json={},  # indicate absence for the synthesis stage
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
    try:
        # Best-effort DSPy configuration for local Ollama models; safe no-op if already configured.
        try:  # pragma: no cover - exercised indirectly in integration/E2E
            import dspy  # type: ignore
            model_name = (os.getenv("AI_FEEDBACK_MODEL") or "").strip()
            if model_name and hasattr(dspy, "LM"):
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
    except Exception:
        # structured path unavailable; proceed to legacy two-stage path
        pass

    analysis_runner = dspy_programs.FeedbackAnalysisProgram(runner=_run_analysis_model)

    try:
        raw_analysis = analysis_runner.run(
            text_md=text_md,
            criteria=criteria,
            teacher_instructions_md=teacher_instructions_md,
            solution_hints_md=solution_hints_md,
        )
    except TimeoutError:
        raise
    except Exception as exc:
        logger.warning("learning.feedback.analysis_model_failed reason=%s", exc.__class__.__name__)
        raw_analysis = None

    analysis_json: Dict[str, Any] | None = None
    embedded_feedback: str | None = None
    if raw_analysis is not None:
        analysis_json, embedded_feedback = _parse_to_v2(raw_analysis, criteria=criteria)
        if analysis_json is None:
            parse_status = "analysis_fallback"
            analysis_json = _build_default_analysis(criteria)
    else:
        parse_status = "analysis_error"
        analysis_json = _build_default_analysis(criteria)

    feedback_runner = dspy_programs.FeedbackSynthesisProgram(runner=_run_feedback_model)
    feedback_md: str | None = None

    try:
        feedback_md = feedback_runner.run(
            text_md=text_md,
            criteria=criteria,
            analysis_json=analysis_json,
            teacher_instructions_md=teacher_instructions_md,
        )
    except TimeoutError:
        raise
    except Exception as exc:
        logger.warning("learning.feedback.feedback_model_failed reason=%s", exc.__class__.__name__)
        feedback_md = None

    if not feedback_md or not feedback_md.strip():
        if embedded_feedback:
            feedback_md = embedded_feedback
            feedback_source = "analysis_embed"
        else:
            if parse_status == "parsed":
                parse_status = "feedback_fallback"
            elif parse_status in {"analysis_fallback", "analysis_error"}:
                parse_status = "analysis_feedback_fallback"
            feedback_md = _default_feedback_md()
            feedback_source = "fallback"

    logger.info(
        "learning.feedback.dspy_pipeline_completed feedback_source=%s parse_status=%s criteria_count=%s",
        feedback_source,
        parse_status,
        len(criteria),
    )

    return FeedbackResult(feedback_md=feedback_md, analysis_json=analysis_json, parse_status=parse_status)
