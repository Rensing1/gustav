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

        Regeln (nur evidenzbasiert):
            - Bewerte jedes Kriterium ausschließlich anhand expliziter Informationen im Schülertext.
            - Erfinde keine Inhalte, die nicht im Text stehen.
            - Wenn du keine ausreichenden Belege für ein Kriterium findest, setze den Score auf 0
              und notiere in der Erklärung „kein Beleg gefunden“.
            - Aufgabenstellung und der lehrkraftseitige KI-Kontext sind nur Kontext: Sie helfen dir zu verstehen,
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
        teacher_context_md: str | None = dspy.InputField(  # type: ignore[attr-defined]
            desc="Lehrkraftseitiger KI-Kontext (Wissensbasis); nur Kontext, nicht im Output zitieren."
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
        teacher_context_md: str | None = None


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
            - Struktur: genau zwei Absätze mit diesen Überschriften (Markdown, fett):
              (1) `**Das ist dir gut gelungen:** ...`
              (2) `**Das kannst du besser:** ...`
            - Stütze dich auf die Analysewerte (`criteria_results`) und die Aufgabenstellung.
            - Der lehrkraftseitige KI-Kontext darf nicht zitiert werden.
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
        teacher_context_md: str | None = dspy.InputField(  # type: ignore[attr-defined]
            desc="Lehrkraftseitiger KI-Kontext (Wissensbasis); nur Kontext, nicht zitieren."
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
        teacher_context_md: str | None = None


# ---------------------------------------------------------------------------
# Visual tasks (image/PDF) — DSPy Signatures
# ---------------------------------------------------------------------------

if dspy is not None and hasattr(dspy, "Signature"):

    class VisualFeedbackAnalysisSignature(dspy.Signature):  # type: ignore[attr-defined]
        """Analysiere eine visuelle Schülerabgabe (Bild/PDF) anhand vorgegebener Kriterien.

        Rolle:
            Du denkst wie eine erfahrene Lehrkraft, die fair und evidenzbasiert
            korrigiert. Du kannst Text *und* grafische Inhalte aus dem Bild
            berücksichtigen.

        Ziel:
            Für jedes Kriterium soll klar erkennbar sein,
            - wie gut das Kriterium erfüllt ist (Score 0..10) und
            - worauf du dich im visuellen Inhalt stützt (kurze Erklärung).

        Regeln (nur evidenzbasiert):
            - Bewerte jedes Kriterium ausschließlich anhand sichtbarer Inhalte.
            - Erfinde keine Inhalte, die nicht erkennbar sind.
            - Wenn du keine ausreichenden Belege findest: Score 0 und Erklärung
              „kein Beleg gefunden“.
            - Aufgabenstellung und der lehrkraftseitige KI-Kontext sind nur Kontext; sie dürfen
              nicht als „Beleg“ herangezogen oder zitiert werden.

        Ausgabe:
            - `overall_score` (0..5) als grobe Gesamteinschätzung.
            - `criteria_results`: Liste von {criterion, max_score=10, score 0..10, explanation_md}.
        """

        student_image: dspy.Image = dspy.InputField(  # type: ignore[attr-defined]
            desc="Schülerabgabe als Bild (data-URI oder URL via dspy.Image)."
        )
        criteria: list[str] = dspy.InputField(  # type: ignore[attr-defined]
            desc="Geordnete Liste der Bewertungs-Kriterien (Strings)."
        )
        teacher_instructions_md: str | None = dspy.InputField(  # type: ignore[attr-defined]
            desc="Aufgabenstellung; nur als Kontext, nicht direkt bewerten."
        )
        teacher_context_md: str | None = dspy.InputField(  # type: ignore[attr-defined]
            desc="Lehrkraftseitiger KI-Kontext (Wissensbasis); nur Kontext, nicht im Output zitieren."
        )

        overall_score: int = dspy.OutputField(  # type: ignore[attr-defined]
            desc="Gesamtwertung 0..5, aus den Kriterien abgeleitet."
        )
        criteria_results: list[CriterionResult] = dspy.OutputField(  # type: ignore[attr-defined]
            desc="Liste von Objekten mit {criterion, max_score, score, explanation_md}."
        )

else:

    @dataclass
    class VisualFeedbackAnalysisSignature:  # type: ignore[no-redef]
        """Fallback visual analysis signature used when DSPy is unavailable."""

        student_image: Any
        criteria: Sequence[str]
        teacher_instructions_md: str | None = None
        teacher_context_md: str | None = None


if dspy is not None and hasattr(dspy, "Signature"):

    class VisualFeedbackSynthesisSignature(dspy.Signature):  # type: ignore[attr-defined]
        """Erzeuge aus visueller Analyse eine kurze Rückmeldung im Fließtext.

        Ziel:
            Formuliere eine kurze, ermutigende Rückmeldung, basierend auf der
            strukturierten Analyse und dem visuellen Inhalt.

        Regeln:
            - Schreibe Fließtext (keine Listen/Bullets).
            - Stütze dich auf die Analyse (`criteria_results`) und sichtbare Inhalte.
            - Erfinde keine Inhalte.
            - Struktur: genau zwei Absätze mit diesen Überschriften (Markdown, fett):
              (1) `**Das ist dir gut gelungen:** ...`
              (2) `**Das kannst du besser:** ...`
        """

        student_image: dspy.Image = dspy.InputField(  # type: ignore[attr-defined]
            desc="Schülerabgabe als Bild (data-URI oder URL via dspy.Image)."
        )
        analysis_json: CriteriaAnalysis = dspy.InputField(  # type: ignore[attr-defined]
            desc="criteria.v2 Analyse, erzeugt durch die vorherige Stufe."
        )
        teacher_instructions_md: str | None = dspy.InputField(  # type: ignore[attr-defined]
            desc="Aufgabenstellung; optionaler Kontext für das Feedback."
        )
        teacher_context_md: str | None = dspy.InputField(  # type: ignore[attr-defined]
            desc="Lehrkraftseitiger KI-Kontext (Wissensbasis); nur Kontext, nicht zitieren."
        )

        feedback_md: str = dspy.OutputField(  # type: ignore[attr-defined]
            desc="Formative Rückmeldung in Markdown (Fließtext, keine Listen)."
        )

else:

    @dataclass
    class VisualFeedbackSynthesisSignature:  # type: ignore[no-redef]
        """Fallback synthesis signature used when DSPy is unavailable."""

        student_image: Any
        analysis_json: dict[str, Any]
        teacher_instructions_md: str | None = None
        teacher_context_md: str | None = None


# ---------------------------------------------------------------------------
# "No criteria" feedback Signatures (skip scoring step)
# ---------------------------------------------------------------------------

if dspy is not None and hasattr(dspy, "Signature"):

    class FeedbackNoCriteriaSignature(dspy.Signature):  # type: ignore[attr-defined]
        """Erzeuge Feedback ohne Kriterienliste.

        Situation:
            Die Lehrkraft hat keine Bewertungskriterien hinterlegt. Es gibt daher
            keine rubric-basierte Auswertung. Du sollst trotzdem eine kurze,
            motivierende Rückmeldung schreiben.

        Regeln:
            - Schreibe genau zwei Absätze mit diesen Überschriften (Markdown, fett):
              (1) `**Das ist dir gut gelungen:** ...`
              (2) `**Das kannst du besser:** ...`
            - Keine Listen/Bullets.
            - Erfinde keine Inhalte; beziehe dich nur auf den Schülertext.
            - Aufgabenstellung und KI-Kontext sind nur Kontext und dürfen nicht zitiert werden.
        """

        student_text_md: str = dspy.InputField(  # type: ignore[attr-defined]
            desc="Schülerabgabe als Markdown-Text."
        )
        teacher_instructions_md: str | None = dspy.InputField(  # type: ignore[attr-defined]
            desc="Aufgabenstellung; optionaler Kontext."
        )
        teacher_context_md: str | None = dspy.InputField(  # type: ignore[attr-defined]
            desc="Lehrkraftseitiger KI-Kontext (Wissensbasis); nur Kontext, nicht zitieren."
        )

        feedback_md: str = dspy.OutputField(  # type: ignore[attr-defined]
            desc="Feedback in Markdown mit genau zwei Absätzen und den festen Überschriften."
        )


    class VisualFeedbackNoCriteriaSignature(dspy.Signature):  # type: ignore[attr-defined]
        """Erzeuge visuelles Feedback ohne Kriterienliste.

        Regeln:
            - Schreibe genau zwei Absätze mit diesen Überschriften (Markdown, fett):
              (1) `**Das ist dir gut gelungen:** ...`
              (2) `**Das kannst du besser:** ...`
            - Keine Listen/Bullets.
            - Erfinde keine Inhalte; beziehe dich nur auf sichtbare Inhalte im Bild/PDF.
            - Aufgabenstellung und KI-Kontext sind nur Kontext und dürfen nicht zitiert werden.
        """

        student_image: dspy.Image = dspy.InputField(  # type: ignore[attr-defined]
            desc="Schülerabgabe als Bild (data-URI oder URL via dspy.Image)."
        )
        teacher_instructions_md: str | None = dspy.InputField(  # type: ignore[attr-defined]
            desc="Aufgabenstellung; optionaler Kontext."
        )
        teacher_context_md: str | None = dspy.InputField(  # type: ignore[attr-defined]
            desc="Lehrkraftseitiger KI-Kontext (Wissensbasis); nur Kontext, nicht zitieren."
        )

        feedback_md: str = dspy.OutputField(  # type: ignore[attr-defined]
            desc="Feedback in Markdown mit genau zwei Absätzen und den festen Überschriften."
        )

else:

    @dataclass
    class FeedbackNoCriteriaSignature:  # type: ignore[no-redef]
        student_text_md: str
        teacher_instructions_md: str | None = None
        teacher_context_md: str | None = None


    @dataclass
    class VisualFeedbackNoCriteriaSignature:  # type: ignore[no-redef]
        student_image: Any
        teacher_instructions_md: str | None = None
        teacher_context_md: str | None = None


# ---------------------------------------------------------------------------
# Vision / OCR Signatures
# ---------------------------------------------------------------------------

if dspy is not None and hasattr(dspy, "Signature"):

    class VisionOcrSignature(dspy.Signature):  # type: ignore[attr-defined]
        """Extrahiere Text aus einer visuellen Schülerabgabe (OCR/Handschrift/Diagramme) als Markdown.

        Ziel:
            Die Ausgabe soll eine möglichst genaue Text-Repräsentation des sichtbaren Inhalts sein,
            damit die Feedback-Pipeline (Text-Analyse + Rückmeldung) darauf arbeiten kann.

        Regeln:
            - Schreibe nur den erkannten Inhalt (keine Bewertung, keine Rückmeldung, keine Meta-Erklärungen).
            - Erfinde keine Inhalte. Wenn etwas unleserlich ist, markiere es kurz als `[unleserlich]`.
            - Behalte Struktur, wenn sinnvoll (Absätze/Zeilenumbrüche). Keine Listenpflicht.
            - Keine Codeblöcke, keine JSON-Ausgabe.

        Ausgabe:
            - `text_md`: erkannter Inhalt als Markdown (Deutsch, sofern im Bild vorhanden).
        """

        student_image: dspy.Image = dspy.InputField(  # type: ignore[attr-defined]
            desc="Schülerabgabe als Bild (data-URI oder URL via dspy.Image)."
        )
        text_md: str = dspy.OutputField(  # type: ignore[attr-defined]
            desc="Erkannter Text als Markdown (ohne zusätzliche Kommentare)."
        )

else:

    @dataclass
    class VisionOcrSignature:  # type: ignore[no-redef]
        student_image: Any
