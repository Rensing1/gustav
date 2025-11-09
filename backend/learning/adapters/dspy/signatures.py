"""
Documentation-only DSPy signature for the feedback analysis program.

Intent:
    Centralise the naming of inputs/outputs (student text, criteria list,
    feedback Markdown, criteria.v2 JSON) so that future DSPy modules can
    import the same signature. In environments where DSPy is not installed,
    we fall back to a simple dataclass to keep tests dependency-light.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

try:  # pragma: no cover - optional runtime dependency
    import dspy  # type: ignore
except Exception:  # pragma: no cover - exercised when tests inject stub
    dspy = None  # type: ignore[assignment]


if dspy is not None and hasattr(dspy, "Signature"):

    class FeedbackAnalysisSignature(dspy.Signature):  # type: ignore[attr-defined]
        """DSPy signature describing our structured feedback contract."""

        student_text_md = dspy.InputField(  # type: ignore[attr-defined]
            desc="Sanitised learner submission in Markdown (not logged)."
        )
        criteria = dspy.InputField(  # type: ignore[attr-defined]
            desc="Ordered list of rubric labels (strings)."
        )

        feedback_md = dspy.OutputField(  # type: ignore[attr-defined]
            desc="Formative feedback in Markdown without PII."
        )
        criteria_results_json = dspy.OutputField(  # type: ignore[attr-defined]
            desc="criteria.v2 JSON structure as string."
        )

else:

    @dataclass
    class FeedbackAnalysisSignature:  # type: ignore[no-redef]
        """Fallback signature used when DSPy is unavailable in tests."""

        student_text_md: str
        criteria: Sequence[str]


if dspy is not None and hasattr(dspy, "Signature"):

    class FeedbackSynthesisSignature(dspy.Signature):  # type: ignore[attr-defined]
        """DSPy signature defining the feedback synthesis contract."""

        student_text_md = dspy.InputField(  # type: ignore[attr-defined]
            desc="Same sanitized learner submission as the analysis stage."
        )
        analysis_json = dspy.InputField(  # type: ignore[attr-defined]
            desc="criteria.v2 JSON produced by the analysis stage."
        )

        feedback_md = dspy.OutputField(  # type: ignore[attr-defined]
            desc="Formative feedback in Markdown referencing the criteria."
        )

else:

    @dataclass
    class FeedbackSynthesisSignature:  # type: ignore[no-redef]
        """Fallback synthesis signature used for docs/tests without DSPy."""

        student_text_md: str
        analysis_json: dict
