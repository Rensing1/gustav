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
        """Analysiere einen Schülertext anhand vorgegebener Kriterien und liefere eine strukturierte Bewertung.

        Rolle:
            Du denkst wie eine erfahrene Lehrkraft, die fair und evidenzbasiert korrigiert.

        Ziel:
            Für jedes Kriterium soll klar erkennbar sein,
            - wie gut das Kriterium erfüllt ist (Score 0..10) und
            - worauf du dich im Schülertext stützt (kurze Erklärung mit Bezug zur Textstelle).
            Zusätzlich berechnest du eine grobe Gesamteinschätzung (overall_score 0..5).

        Regeln (evidence-only):
            - Bewerte jedes Kriterium ausschließlich anhand expliziter Informationen im Schülertext.
            - Erfinde keine Inhalte, die nicht im Text stehen.
            - Wenn du keine ausreichenden Belege für ein Kriterium findest, setze den Score auf 0
              und notiere in der Erklärung „kein Beleg gefunden“.
            - Aufgabenstellung und Lösungshinweise sind nur Kontext: Sie helfen dir zu verstehen,
              worum es in der Aufgabe geht, dürfen aber weder zitiert noch als Begründung verwendet werden.

        Skalen:
            - criteria_results[i].score: ganze Zahl von 0 bis 10.
              0 = nicht erfüllt/kein Beleg, 5 = teilweise erfüllt, 10 = sehr gut erfüllt.
            - overall_score: ganze Zahl von 0 bis 5, abgeleitet aus allen Kriterien
              (0 = insgesamt schwach, 3 = gemischt, 5 = insgesamt sehr gut).

        Ausgabe:
            - `overall_score` (0..5) als grobe Gesamteinschätzung.
            - `criteria_results`: Liste von Objekten mit
              `criterion` (Kriteriumsname), `max_score` (Standard 10),
              `score` (0..10) und `explanation_md`.
            - `explanation_md` ist eine kurze, sachliche Erklärung in Markdown
              (1–3 Sätze, auf Deutsch, mit Bezug zum Kriterium und zur Textstelle).

        Hinweis zur Pipeline:
            Die Signature liefert nur `overall_score` und `criteria_results`. Der umgebende
            Python-Code (CriteriaAnalysis + Parser) ergänzt das Feld `schema="criteria.v2"`
            und normalisiert die Struktur in das endgültige `criteria.v2`-JSON.
        """

        student_text_md: str = dspy.InputField(  # type: ignore[attr-defined]
            desc="Schülerabgabe als Markdown-Text (wird nicht geloggt)."
        )
        criteria: list[str] = dspy.InputField(  # type: ignore[attr-defined]
            desc="Geordnete Liste der Bewertungs-Kriterien (Strings)."
        )
        teacher_instructions_md: str | None = dspy.InputField(  # type: ignore[attr-defined]
            desc="Aufgabenstellung; nur als Kontext, nicht direkt bewerten."
        )
        solution_hints_md: str | None = dspy.InputField(  # type: ignore[attr-defined]
            desc="Lösungshinweise der Lehrkraft; nur Kontext, nicht im Output zitieren."
        )

        overall_score: int = dspy.OutputField(  # type: ignore[attr-defined]
            desc="Gesamtwertung 0..5, aus den Kriterien abgeleitet."
        )
        criteria_results: list[CriterionResult] = dspy.OutputField(  # type: ignore[attr-defined]
            desc="Liste von Objekten mit {criterion, max_score, score, explanation_md}."
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
        """Erzeuge aus der Analyse eine kurze, pädagogisch sinnvolle Rückmeldung im Fließtext.

        Rolle:
            Du bist eine unterstützende Lehrkraft, die Stärken würdigt und konkrete
            nächste Schritte aufzeigt, ohne zu demotivieren.

        Ziel:
            Aus der strukturierten Analyse (`criteria.v2`) und der Aufgabenstellung soll
            ein gut lesbarer Rückmeldungstext in Markdown entstehen, der
            - zuerst hervorhebt, was gelungen ist, und
            - danach konkret beschreibt, was der/die Schüler:in verbessern kann.

        Regeln:
            - Schreibe ausschließlich Fließtext (keine Listen/Bullets).
            - Struktur: zwei klar erkennbare Teile
              (1) Stärken („Was war gut?“),
              (2) Verbesserungsmöglichkeiten („Was kann beim nächsten Mal besser werden?“).
            - Stütze dich auf die Analysewerte (`criteria_results`) und die Aufgabenstellung.
            - Lösungshinweise der Lehrkraft dürfen nicht zitiert werden.
            - Wiederhole den Schülertext nicht vollständig; formuliere kurz, konkret
              und ermutigend in deutscher Sprache.

        Ausgabe:
            - `feedback_md`: zusammenhängender Markdown-Fließtext, der sich direkt an
              die lernende Person richtet und zum Weiterarbeiten motiviert.
        """

        student_text_md: str = dspy.InputField(  # type: ignore[attr-defined]
            desc="Schülerabgabe in derselben Form wie in der Analyse-Stufe."
        )
        analysis_json: CriteriaAnalysis = dspy.InputField(  # type: ignore[attr-defined]
            desc="criteria.v2 JSON-Analyse, erzeugt durch die vorherige Stufe."
        )
        teacher_instructions_md: str | None = dspy.InputField(  # type: ignore[attr-defined]
            desc="Aufgabenstellung; optionaler Kontext für das Feedback."
        )

        feedback_md: str = dspy.OutputField(  # type: ignore[attr-defined]
            desc="Formative Rückmeldung in Markdown (Fließtext, keine Listen)."
        )

else:

    @dataclass
    class FeedbackSynthesisSignature:  # type: ignore[no-redef]
        """Fallback synthesis signature used for docs/tests without DSPy."""

        student_text_md: str
        analysis_json: dict[str, Any]
        teacher_instructions_md: str | None = None
