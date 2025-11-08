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
from typing import Any, Dict, Sequence


def _build_prompt(*, text_md: str, criteria: Sequence[str]) -> str:
    """Build a simple, privacy‑aware instruction and output contract.

    Emphasises:
    - No leakage of student text in the response.
    - Output must be JSON following criteria.v2 schema (loosely described).
    - Criteria names are included so the model can align explanations.
    """
    crit_lines = "\n".join(f"- {str(c)}" for c in criteria)
    return (
        "Role: Teacher. Provide formative feedback.\n"
        "Privacy: Do not include student text in the output.\n"
        "Output: JSON following schema 'criteria.v2' with keys: score (0..5), "
        "criteria_results (array of objects: criterion, max_score, score, explanation_md).\n"
        "Criteria (ordered):\n" + crit_lines + "\n"
        "Only return the JSON, no prose."
    )


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
    raw = client.generate(model=model_name, prompt=prompt, options={"timeout": timeout})
    if isinstance(raw, dict):
        response = raw.get("response") or raw.get("message")
        if isinstance(response, str):
            return response
        return json.dumps(raw)
    if isinstance(raw, str):
        return raw
    return json.dumps(raw)


def _run_model(*, text_md: str, criteria: Sequence[str]) -> str:
    """Run the (mockable) LM call using a structured prompt.

    Tests may monkeypatch this function directly or the `_lm_call` shim to
    intercept prompt content and return tailored outputs.
    """
    prompt = _build_prompt(text_md=text_md, criteria=criteria)
    timeout = int(os.getenv("AI_TIMEOUT_FEEDBACK", "30"))
    return _lm_call(prompt=prompt, timeout=timeout)


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
    try:
        obj = json.loads(raw)
    except Exception:
        return None, None

    feedback_val = obj.get("feedback_md") or obj.get("feedback") or obj.get("feedback_markdown")
    feedback_md = feedback_val.strip() if isinstance(feedback_val, str) and feedback_val.strip() else None

    # Extract candidate items list with field variants
    items_raw = obj.get("criteria_results") or obj.get("criteria") or []
    by_name: Dict[str, Dict[str, Any]] = {}
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
        by_name[str(name)] = {
            "criterion": str(name),
            "max_score": max_i,
            "score": sc_i,
            "explanation_md": str(expl) if expl else f"Bezug zum Kriterium „{name}“",
        }

    # Build normalized list following requested ordering and fill missing
    norm_items: list[Dict[str, Any]] = []
    for name in criteria:
        if str(name) in by_name:
            norm_items.append(by_name[str(name)])
        else:
            norm_items.append(
                {
                    "criterion": str(name),
                    "max_score": 10,
                    "score": 6,
                    "explanation_md": f"Bezug zum Kriterium „{str(name)}“",
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


def analyze_feedback(*, text_md: str, criteria: Sequence[str]) -> tuple[str, dict]:
    """Produce minimal Markdown feedback and criteria.v2 analysis via DSPy path.

    Why:
        The local adapter prefers a DSPy‑based flow when the module is
        importable. This function centralises the behavior, keeping the
        adapter narrow and easy to test.

    Parameters:
        text_md: Learner submission as Markdown (not logged here).
        criteria: Ordered list of criteria names.

    Returns:
        A tuple of `(feedback_md, analysis_json)` where `analysis_json` follows
        the `criteria.v2` schema.
    """
    # NOTE: Import dspy shallowly to select this program only when available.
    try:  # pragma: no cover - presence is tested from adapter, not here
        import dspy  # type: ignore
        _ = getattr(dspy, "__version__", None)  # touch to prove availability
    except Exception:
        # If import fails at this layer, let callers fall back to non‑DSPy path.
        raise ImportError("dspy is not available")

    # Execute pseudo model and parse
    raw = _run_model(text_md=text_md, criteria=criteria)

    if not criteria:
        # Keep contract simple for MVP: no criteria → empty list, overall 0
        return (
            "**Rückmeldung**\n\n- Bitte Kriterien definieren, um eine Bewertung zu erhalten.",
            {"schema": "criteria.v2", "score": 0, "criteria_results": []},
        )

    parsed, feedback_override = _parse_to_v2(raw, criteria=criteria)
    if parsed is None:
        # Fallback deterministic structure
        crit_items = [
            {
                "criterion": str(name),
                "max_score": 10,
                "score": 6,
                "explanation_md": f"Bezug zum Kriterium „{str(name)}“",
            }
            for name in criteria
        ]
        analysis = {"schema": "criteria.v2", "score": 3, "criteria_results": crit_items}
    else:
        analysis = parsed

    default_feedback = (
        "**Rückmeldung**\n\n"
        "- Stärken: klar benannt.\n"
        "- Nächste Schritte: einzelne Kriterien gezielt verbessern."
    )
    feedback_md = feedback_override or default_feedback
    return feedback_md, analysis
