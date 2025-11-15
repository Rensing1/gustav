"""
DSPy Signatures for structured learning feedback (analysis → synthesis).

KISS:
    - Minimal inputs/outputs, clear field names.
    - Fallback dataclasses when DSPy isn't importable to keep tests light.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

try:  # pragma: no cover - optional runtime dependency
    import dspy  # type: ignore
except Exception:  # pragma: no cover - exercised when tests inject stub
    dspy = None  # type: ignore[assignment]


from backend.learning.adapters.dspy.types import CriteriaAnalysis, CriterionResult

if dspy is not None and hasattr(dspy, "Signature"):

    class FeedbackAnalysisSignature(dspy.Signature):  # type: ignore[attr-defined]
        """Analyse eines Schülertextes anhand vorgegebener Kriterien (strukturierte Ausgabe).

        Regeln (evidence-only):
        - Bewerte jedes Kriterium ausschließlich anhand expliziter Belege im Schülertext.
        - Wenn kein Beleg vorhanden ist, vergebe Score 0 und notiere „kein Beleg gefunden“.
        - Gib pro Kriterium eine kurze, objektive Erklärung und nenne prägnant die Passage oder „kein Beleg gefunden“.
        - Lösungshinweise und Lehrer-Instruktionen dienen nur als Kontext; sie dürfen nicht in die Bewertung einfließen oder zitiert werden.

        Ausgabe:
        - `overall_score` (0..5) als grobe Gesamteinschätzung.
        - `criteria_results`: Liste von Objekten mit `criterion`, `max_score`=10, `score` (0..10), `explanation_md`.
        - Es wird kein Fließtext außerhalb dieser Felder zurückgegeben.
        """

        student_text_md: str = dspy.InputField(  # type: ignore[attr-defined]
            desc="Learner submission in Markdown (not logged)."
        )
        criteria: list[str] = dspy.InputField(  # type: ignore[attr-defined]
            desc="Ordered list of rubric labels (strings)."
        )
        teacher_instructions_md: str | None = dspy.InputField(  # type: ignore[attr-defined]
            desc="Task instructions; context only; do not grade"
        )
        solution_hints_md: str | None = dspy.InputField(  # type: ignore[attr-defined]
            desc="Teacher solution hints; context only; do not leak"
        )

        overall_score: int = dspy.OutputField(  # type: ignore[attr-defined]
            desc="Overall 0..5 computed from criteria"
        )
        criteria_results: list[CriterionResult] = dspy.OutputField(  # type: ignore[attr-defined]
            desc="List of {criterion, max_score, score, explanation_md}"
        )

else:

    @dataclass
    class FeedbackAnalysisSignature:  # type: ignore[no-redef]
        """Fallback signature used when DSPy is unavailable in tests."""

        student_text_md: str
        criteria: Sequence[str]
        teacher_instructions_md: str | None = None
        solution_hints_md: str | None = None


if dspy is not None and hasattr(dspy, "Signature"):

    class FeedbackSynthesisSignature(dspy.Signature):  # type: ignore[attr-defined]
        """Erzeuge eine pädagogisch wertvolle Rückmeldung (Fließtext) aus der Analyse.

        Regeln:
        - Schreibe ausschließlich Fließtext (keine Listen/Bullets).
        - Zwei klar erkennbare Abschnitte: (1) Was war gut? (2) Was kann verbessert werden?
        - Stütze dich auf die Analysewerte und die Aufgabenstellung; die Lösungshinweise dürfen nicht zitiert werden.
        - Widerhole den Schülertext nicht vollständig; formuliere kurz, konkret und ermutigend.
        """

        student_text_md: str = dspy.InputField(  # type: ignore[attr-defined]
            desc="Same learner submission as the analysis stage"
        )
        analysis_json: CriteriaAnalysis = dspy.InputField(  # type: ignore[attr-defined]
            desc="criteria.v2 JSON produced by analysis"
        )
        teacher_instructions_md: str | None = dspy.InputField(  # type: ignore[attr-defined]
            desc="Task instructions; optional context"
        )

        feedback_md: str = dspy.OutputField(  # type: ignore[attr-defined]
            desc="Formative feedback in Markdown (prose, no lists)"
        )

else:

    @dataclass
    class FeedbackSynthesisSignature:  # type: ignore[no-redef]
        """Fallback synthesis signature used for docs/tests without DSPy."""

        student_text_md: str
        analysis_json: dict[str, Any]
        teacher_instructions_md: str | None = None
