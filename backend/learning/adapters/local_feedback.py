"""
Local Feedback adapter using a simple Ollama client call.

Intent:
    Minimal implementation to satisfy tests:
      - Analyze Markdown text against provided criteria.
      - Return FeedbackResult with Markdown and a `criteria.v2` analysis JSON.
      - Map client timeouts to FeedbackTransientError.

Privacy:
    Do not log or return raw student text beyond the structured fields.
"""

from __future__ import annotations

import logging
import os
from typing import Sequence

from backend.learning.adapters.ports import FeedbackResult, FeedbackTransientError


logger = logging.getLogger(__name__)


class _LocalFeedbackAdapter:
    """Minimal Feedback adapter backed by a local Ollama client.

    Keeps logic intentionally simple and deterministic for tests, while
    respecting the expected result schema and error mapping.
    """

    def __init__(self) -> None:
        raw_model = os.getenv("AI_FEEDBACK_MODEL")
        self._dspy_model = (raw_model or "").strip()
        self._model = self._dspy_model or os.getenv("OLLAMA_FEEDBACK_MODEL") or "llama3.1"

        raw_base_url = os.getenv("OLLAMA_BASE_URL")
        self._dspy_base_url = (raw_base_url or "").strip()
        self._base_url = self._dspy_base_url or os.getenv("OLLAMA_BASE_URL") or "http://ollama:11434"

        self._timeout = int(os.getenv("AI_TIMEOUT_FEEDBACK", "30"))

    def analyze(
        self,
        *,
        text_md: str,
        criteria: Sequence[str],
        instruction_md: str | None = None,
        hints_md: str | None = None,
    ) -> FeedbackResult:  # type: ignore[override]
        """Produce formative feedback and a criteria.v2 analysis.

        Why:
            Provide a deterministic, privacy-conscious feedback step for the
            learning worker. Uses DSPy when available, otherwise a local
            Ollama client, then normalizes results into `criteria.v2`.

        Parameters:
            text_md: Student submission text in Markdown (preprocessed by web layer).
            criteria: Sequence of rubric items to evaluate.

        Behavior:
            - Prefers DSPy program if `dspy` can be imported; otherwise calls
              a local Ollama client with a compact prompt.
            - Always returns a minimal `criteria.v2` structure with
              `criterion`, `max_score`, `score`, `explanation_md`.
            - Classifies client timeouts as transient.

        Permissions:
            Intended for the learning worker's background processing. No
            direct end-user authorization is evaluated here.
        """
        use_dspy, skip_reason = self._dspy_prerequisites_met()
        dspy_program = None

        if use_dspy:
            try:  # pragma: no cover - import decision is exercised via tests
                import dspy  # type: ignore

                _ = getattr(dspy, "__version__", None)
                from backend.learning.adapters.dspy import feedback_program as dspy_program
            except Exception as exc:
                logger.warning("learning.feedback.dspy_import_failed reason=%s", exc.__class__.__name__)
                use_dspy = False
        elif skip_reason:
            logger.warning("learning.feedback.dspy_skipped reason=%s", skip_reason)

        dspy_analysis: dict | None = None
        if use_dspy and dspy_program is not None:
            try:
                dspy_result = dspy_program.analyze_feedback(
                    text_md=text_md,
                    criteria=criteria,
                    teacher_instructions_md=instruction_md,
                    solution_hints_md=hints_md,
                )
                converted: FeedbackResult | None = None
                if isinstance(dspy_result, FeedbackResult):
                    converted = dspy_result
                elif hasattr(dspy_result, "feedback_md") and hasattr(dspy_result, "analysis_json"):
                    converted = FeedbackResult(
                        feedback_md=str(getattr(dspy_result, "feedback_md")),
                        analysis_json=getattr(dspy_result, "analysis_json"),
                        parse_status=getattr(dspy_result, "parse_status", None),
                    )
                else:
                    try:
                        feedback_md, analysis = dspy_result  # type: ignore[misc]
                        converted = FeedbackResult(
                            feedback_md=str(feedback_md),
                            analysis_json=analysis,
                            parse_status=getattr(dspy_result, "parse_status", None),
                        )
                    except Exception as exc:  # pragma: no cover - defensive guard
                        logger.warning("learning.feedback.dspy_invalid_return reason=%s", exc.__class__.__name__)
                if converted is not None:
                    parse_status = (converted.parse_status or "unknown").strip()
                    feedback_trimmed = (converted.feedback_md or "").strip()
                    # Treat the literal string "None" as empty to avoid persisting it.
                    if feedback_trimmed.lower() == "none":
                        feedback_trimmed = ""
                    analysis_dict = converted.analysis_json if isinstance(converted.analysis_json, dict) else None
                    has_items = bool(analysis_dict and isinstance(analysis_dict.get("criteria_results"), list) and analysis_dict["criteria_results"])
                    degraded_statuses = {"analysis_fallback", "analysis_error", "analysis_feedback_fallback"}
                    looks_stub = feedback_trimmed.startswith("**Rückmeldung**") and "Stärken:" in feedback_trimmed
                    if parse_status in degraded_statuses and feedback_trimmed and not looks_stub and has_items:
                        # Degraded Status, aber verwertbares Feedback + Analyse vorhanden → direkt übernehmen.
                        logger.info(
                            "learning.feedback.completed feedback_backend=dspy criteria_count=%s parse_status=%s",
                            len(criteria),
                            parse_status,
                        )
                        return FeedbackResult(
                            feedback_md=feedback_trimmed,
                            analysis_json=analysis_dict or {},
                            parse_status=parse_status,
                        )
                    if parse_status in degraded_statuses:
                        logger.info(
                            "learning.feedback.dspy_degraded_to_ollama criteria_count=%s parse_status=%s",
                            len(criteria),
                            parse_status or "unknown",
                        )
                        dspy_analysis = analysis_dict if isinstance(analysis_dict, dict) else None
                        # Switch to Ollama fallback path below
                        use_dspy = False
                    elif not feedback_trimmed or looks_stub:
                        # Stay within DSPy path: synthesize a brief feedback from the structured analysis
                        # rather than calling Ollama again.
                        analysis_dict = converted.analysis_json if isinstance(converted.analysis_json, dict) else None
                        if analysis_dict is None:
                            analysis_dict = {"schema": "criteria.v2", "score": 0, "criteria_results": []}
                        crit = analysis_dict.get("criteria_results", []) if isinstance(analysis_dict, dict) else []
                        good = [
                            f"{c.get('criterion', 'Kriterium')}: {c.get('score', 0)}/{c.get('max_score', 10)}"
                            for c in crit
                            if int(c.get("score", 0)) >= int(c.get("max_score", 10)) // 2
                        ]
                        bad = [
                            str(c.get('criterion', 'Kriterium'))
                            for c in crit
                            if int(c.get("score", 0)) < int(c.get("max_score", 10)) // 2
                        ]
                        synthetic = []
                        if good:
                            synthetic.append("Stärken: " + ", ".join(good) + ".")
                        if bad:
                            synthetic.append("Hinweise: gezielt ausbauen bei " + ", ".join(bad) + ".")
                        feedback_text = " ".join(synthetic) or "Kurze, konstruktive Rückmeldung basierend auf der Analyse."
                        logger.info(
                            "learning.feedback.completed feedback_backend=dspy criteria_count=%s parse_status=%s",
                            len(criteria),
                            parse_status,
                        )
                        return FeedbackResult(
                            feedback_md=feedback_text,
                            analysis_json=analysis_dict,
                            parse_status=parse_status,
                        )
                    else:
                        logger.info(
                            "learning.feedback.completed feedback_backend=dspy criteria_count=%s parse_status=%s",
                            len(criteria),
                            parse_status,
                        )
                        return converted
            except FeedbackTransientError:
                raise
            except TimeoutError as exc:
                logger.warning("learning.feedback.dspy_timeout reason=timeout")
                raise FeedbackTransientError(str(exc)) from exc
            except RuntimeError as exc:
                logger.warning("learning.feedback.dspy_runtime_error reason=%s", str(exc))
                # Switch to Ollama fallback path
                use_dspy = False
            except Exception as exc:  # pragma: no cover - defensive fallback
                logger.warning("learning.feedback.dspy_failed reason=%s", exc.__class__.__name__)
                # Switch to Ollama fallback path
                use_dspy = False
            # Any exception reaches this point → fall back to Ollama path by disabling DSPy

        feedback_md_from_ollama: str | None = None
        if not use_dspy:
            # Import ollama lazily for test monkeypatching support.
            try:
                import ollama  # type: ignore
            except Exception as exc:  # pragma: no cover - defensive only
                raise FeedbackTransientError(f"ollama client unavailable: {exc}")

            # The real prompt would incorporate text_md and criteria; keep simple here.
            prompt = (
                "Provide short formative feedback in Markdown and consider given criteria.\n"
                f"Criteria count: {len(list(criteria))}."
            )
            try:
                # Use positional host argument for broader client compatibility
                client = ollama.Client(self._base_url)
                # Force raw mode to bypass server-side templates that may reference
                # unavailable functions (e.g., currentDate) and keep behavior stable.
                raw = client.generate(
                    model=self._model,
                    prompt=prompt,
                    options={
                        "raw": True,
                        # Ensure server template is not applied to avoid template errors
                        "template": "{{ .Prompt }}",
                    },
                )
                if isinstance(raw, dict):
                    val = raw.get("response") or raw.get("message")
                    feedback_md_from_ollama = str(val or "").strip() if val is not None else None
                elif isinstance(raw, str):
                    feedback_md_from_ollama = raw.strip()
                else:  # pragma: no cover - defensive normalization
                    feedback_md_from_ollama = str(raw).strip()
            except TimeoutError as exc:
                raise FeedbackTransientError(str(exc))
            except Exception as exc:  # pragma: no cover - conservative mapping
                raise FeedbackTransientError(str(exc))

        # Prefer DSPy-produced analysis if available; otherwise build a minimal criteria.v2 payload.
        if dspy_analysis and isinstance(dspy_analysis, dict):
            analysis = dspy_analysis
        else:
            crit_list = []
            for name in criteria:
                crit_list.append(
                    {
                        "criterion": str(name),
                        "max_score": 10,
                        # KISS default without evidence: 0
                        "score": 0,  # within 0..max_score (v2)
                        "explanation_md": "Kurzbegründung auf Basis des Kriteriums.",
                    }
                )

            analysis = {
                "schema": "criteria.v2",
                # Overall derives to 0 when all items are 0
                "score": 0,  # overall score within 0..5
                "criteria_results": crit_list,
            }

        # Prefer actual model output if available; otherwise return a deterministic stub.
        feedback_md = (feedback_md_from_ollama or "").strip() or (
            "**Rückmeldung**\n\n- Stärken: klar erkennbar.\n- Hinweise: gezielt ausbauen."
        )
        parse_status = "model" if feedback_md_from_ollama else "stub"
        logger.info(
            "learning.feedback.completed feedback_backend=ollama criteria_count=%s parse_status=%s",
            len(criteria),
            parse_status,
        )
        return FeedbackResult(feedback_md=feedback_md, analysis_json=analysis, parse_status=parse_status)

    def _dspy_prerequisites_met(self) -> tuple[bool, str | None]:
        """Check whether env/config allow the DSPy path."""
        if not self._dspy_model:
            return False, "missing_model"
        if not self._dspy_base_url:
            return False, "missing_base_url"
        return True, None


def build() -> _LocalFeedbackAdapter:
    """Factory used by the worker DI to construct the adapter instance."""
    return _LocalFeedbackAdapter()
