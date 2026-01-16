# Plan: Learning AI — nur DSPy (Feedback + Vision-Textextraktion/OCR) über OpenAI-kompatiblen Endpoint (ohne Ollama)

Aktualisierung (2026-01-13):
- Erweitert den bisherigen „DSPy-only Feedback“-Plan, sodass auch **direkte Ollama-Calls für Vision/OCR** entfernt werden.
- Wechselt von Ollama-spezifischer Konfiguration auf **einen einzigen OpenAI-kompatiblen Endpoint** (z.B. Lemonade/Open-WebUI-Proxy), den Betreiber frei konfigurieren können.

## Kontext
Die Learning-AI-Implementierung hat aktuell zwei Formen von Ollama-Kopplung:

1) **Feedback** ist hybrid:
   - Ein DSPy-Structured Path (Signatures + `dspy.Predict`) existiert, aber
   - Legacy-Prompt-Builder und direkte `ollama`-Calls existieren weiterhin als Fallbacks.

2) **Vision-Textextraktion** („OCR“/Handschrift/Diagramme) ruft den `ollama`-Python-Client noch direkt auf.

Dieses Setup ist operativ unnötig komplex (Konfigurationskomplexität, Portabilität, Performance-Tuning) und verhindert, dass Betreiber ihre eigene OpenAI-kompatible LLM/VLM-Runtime (z.B. Lemonade) durch simples Konfigurieren nutzen können:
- ein Endpoint in `.env`, und
- Modellnamen für unterschiedliche Zwecke (Text-Feedback, OCR, visuelles Feedback).

Dieses Dokument ersetzt `docs/plan/2025-11-18-dspy-only-feedback-pipeline.md` und erweitert die „nur DSPy, fail-fast + retry“-Semantik auch auf Vision-Textextraktion/OCR.

## Entscheidungen
1. **Ein OpenAI-kompatibler Endpoint für alle Modelle**
   - Ein Endpoint wird für Text-Modelle und Vision-Modelle (VLMs) geteilt; pro Use-Case ändert sich nur der Modellname.
   - Umgebungsvariablen (hartes Breaking Change):
     - `OPENAI_BASE_URL` (erforderlich): OpenAI-kompatible Base URL **as-is** (keine Pfad-Regeln, kein implizites Anhängen von `/v1`). Beispiel: `http://host.docker.internal:8111/api/v1`
     - `OPENAI_API_KEY` (optional): API-Key/Token (manche Server benötigen keinen)
   - Modell-Selektoren (hartes Breaking Change):
     - `AI_TEXT_MODEL` (erforderlich): ein Modell für beide Text-Schritte (Analyse → Synthese)
     - `AI_OCR_MODEL` (erforderlich): Modell für Vision-Textextraktion (OCR/Handschrift)
     - `AI_VISUAL_MODEL` (erforderlich): Modell für visuelles Feedback (Bild/PDF → Analyse → Feedback), **kein Fallback**
   - Temperaturen pro Modell (hartes Breaking Change; float, wird an `dspy.LM(..., temperature=...)` übergeben):
     - `AI_TEXT_TEMPERATURE` (Default `0.0`)
     - `AI_OCR_TEMPERATURE` (Default `0.0`)
     - `AI_VISUAL_TEMPERATURE` (Default `0.0`)
   - Entfernt (von Learning-Codepfaden nicht mehr unterstützt): `AI_BACKEND`, `OLLAMA_BASE_URL`, `OLLAMA_HOST`, `OLLAMA_API_BASE`, `AI_FEEDBACK_MODEL`, `AI_VISION_MODEL`.

2. **Nur-DSPy-Orchestrierung für Learning AI**
   - Keine Prompt-Builder-Templates als zweiter Prompt-Vertrag.
   - Keine direkten `ollama`-Client-Calls in Learning-Adaptern (Feedback *und* Vision).
   - Kein globales `dspy.configure(...)` (Worker nutzt Threadpool; globaler mutable State bricht parallele, per-Modell Ausführung). Stattdessen `dspy.context(...)` pro Job.

3. **DSPy-Signatures sind die einzige Prompt-/Vertragsquelle**
   - Feedback nutzt weiterhin die bestehenden Signatures.
   - Vision-Textextraktion bekommt eine eigene Signature, die Markdown-Text ausgibt.

4. **Keine deterministischen Fallback-Ausgaben**
   - Wenn strukturierte Analyse/Feedback (oder OCR-Textextraktion) nicht erzeugt werden kann: Fehler werfen.
   - Retries macht der Worker; wir erfinden keine Default-Analyse/Default-Feedback/Default-OCR-Texte.
   - Entfernt explizit den aktuellen „synthetic prose“-Fallback (Feedback-Text aus `analysis_json` zusammenbauen, wenn `feedback_md` fehlt).

5. **DSPy und Konfiguration sind Pflicht**
   - Wenn `dspy` fehlt oder required ENV fehlt → Reason-Code loggen und Fehler werfen (Worker retry).

6. **Leere Kriterienliste ist erlaubt (nur Feedback)**
   - Wenn eine Lehrkraft keine Rubrik-Kriterien angibt, darf trotzdem Feedback erzeugt werden.
   - Der kriteriumsbasierte Scoring-Schritt wird übersprungen und `analysis_json` ist `{}`.

7. **Kein zusätzliches Input-Clipping in Learning AI**
   - Die HTTP-Schicht erzwingt bereits `text_body <= 65_536` Zeichen für Text-Submissions.
   - DSPy-Code kürzt Inputs nicht selbst (vermeidet „hidden behavior“).
   - OCR-Outputs müssen ebenfalls das 65_536-Zeichen-Limit einhalten; wenn ein Modell mehr liefert: transient error (retry).
   - Entfernt explizit Prompt-Clipping-Helfer in DSPy-Programmen (z.B. `_clip(...)`), damit Verhalten transparent und single-sourced bleibt.

8. **DSPy-Caching bleibt aktiv (performance-kritisch)**
   - DSPy-Cache muss für Inferenz-Speed aktiv bleiben (Disk + Memory).
   - Disk-Cache wird nur im `learning-worker`-Container konfiguriert (kein Volume-Mount; Speicherung im Container-Dateisystem):
     - `DSPY_CACHEDIR=/tmp/dspy_cache`
     - `DSPY_CACHE_LIMIT=34359738368` (32 GiB)
   - `disable_history=True`, um keine Prompt/Response-Historie im Speicher zu halten (Privacy + Memory).

9. **Prompt-Sprache: Deutsch (für Schülerabgaben)**
   - Prompt-Inhalte (insb. DSPy-Signature-Docstrings sowie `InputField`/`OutputField`-Beschreibungen) sind deutsch, da Schülerabgaben deutsch sind.
   - Entwickler-Kommentare/technische Docstrings (die nicht als Prompt-Vertrag dienen) bleiben gemäß Repo-Standard englisch.

## User Story
**Als** Betreiber (self-hosted School-Admin) und Product Owner\
**möchte ich**, dass Learning AI (Vision-Textextraktion/OCR + Feedback) ausschließlich über DSPy und einen OpenAI-kompatiblen Endpoint erzeugt wird,\
**damit** Deployments portabel bleiben (Lemonade/OAI-kompatible Server), die Modellwahl via `.env` konfigurierbar ist, der Code lehrbar bleibt (ein Prompt-Vertrag), und Fehler konsistent via Retries statt „hidden fallbacks“ behandelt werden.

## Umfang
### Im Scope
- Text-Feedback-Pipeline (Analyse → Feedback) für Learning-Submissions:
  - `backend/learning/adapters/local_feedback.py`
  - `backend/learning/adapters/dspy/feedback_program.py`
  - `backend/learning/adapters/dspy/programs.py`
  - `backend/learning/adapters/dspy/signatures.py`
- Visuelle Feedback-Pipeline (Bild/PDF → Analyse → Feedback):
  - `backend/learning/adapters/local_feedback.py` (`analyze_visual`)
  - `backend/learning/adapters/dspy/visual_feedback_program.py`
  - `backend/learning/adapters/dspy/programs.py`
  - `backend/learning/adapters/dspy/signatures.py`
- Vision-Textextraktion (Bild/PDF → Markdown-Text) via DSPy-Signature:
  - `backend/learning/adapters/local_vision.py` (direkte `ollama`-Calls entfernen)
  - `backend/learning/adapters/dspy/signatures.py` (`VisionOcrSignature`)
  - `backend/learning/adapters/dspy/vision_program.py` (`extract_text_from_image(...)`)
- Konsolidierung der Konfiguration:
  - `backend/learning/config.py` (nur DI/Adapter-Selektion; Modell-/Endpoint-Konfiguration liegt in den Adaptern)
  - `backend/learning/adapters/local_feedback.py` / `backend/learning/adapters/local_vision.py`:
    - LM-Instanzen aus `OPENAI_BASE_URL` + Modellname bauen und pro Prozess cachen
    - jede Ausführung in `dspy.context(lm=..., disable_history=True, ...)` kapseln (thread-safe)
  - `.env.example` und `docker-compose.yml` ausrichten (dokumentiert + getestet)
- Tests anpassen, sodass die neue Semantik abgebildet ist (TDD: Rot → Grün → Refactor).
- Dokumentation ausrichten:
  - `docs/references/LLM-Prompts.md`
  - `docs/references/learning_ai.md` („Ollama-only“-Wording entfernen; Endpoint+Modelle dokumentieren)

### Außerhalb des Scopes
- UI-Verhalten (Studenten-/Lehrer-Seiten).
- Weitere API-/Schema-Änderungen, außer dem notwendigen Rename für den KI-Kontext:
  - `hints_md` → `teacher_context_md` (DB + OpenAPI; teacher-only, niemals im Student-DTO).

## Aktuelle DSPy-Bausteine (Ist-Zustand)
Dieser Abschnitt ist ein originalgetreuer Snapshot der aktuellen DSPy-Prompt-Verträge und Programm-Entrypoints im Repo.
Er dient als Baseline, bevor wir Signatures/Programme optimieren.

### Signatures (aktuell)
Quelle: `backend/learning/adapters/dspy/signatures.py` (Auszug: nur DSPy-`Signature`-Klassen; Fallback-Dataclasses aus Gründen der Kürze ausgelassen).

```python
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
```

### Programme / Module (aktuell)
Quellen:
- `backend/learning/adapters/dspy/programs.py`
- `backend/learning/adapters/dspy/vision_program.py`

```python
"""DSPy program scaffolding for learning feedback (analysis → synthesis)."""

from __future__ import annotations

from typing import Any, Callable, Sequence

from backend.learning.adapters.dspy.signatures import (
    FeedbackAnalysisSignature,
    FeedbackNoCriteriaSignature,
    FeedbackSynthesisSignature,
    VisualFeedbackAnalysisSignature,
    VisualFeedbackNoCriteriaSignature,
    VisualFeedbackSynthesisSignature,
)
from backend.learning.adapters.dspy.types import CriteriaAnalysis, CriterionResult


def _ensure_criteria_results(value: Any) -> list[CriterionResult]:
    if value is None:
        return []
    if isinstance(value, list):
        return [CriterionResult.from_value(item) for item in value]
    return [CriterionResult.from_value(value)]


def run_structured_analysis(
    *,
    text_md: str,
    criteria: Sequence[str],
    teacher_instructions_md: str | None = None,
    teacher_context_md: str | None = None,
) -> CriteriaAnalysis:
    """Execute DSPy Predict(Signature) to obtain structured analysis data."""
    try:  # pragma: no cover - exercised via tests
        import dspy  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise ImportError(f"dspy unavailable: {exc}")

    predict = dspy.Predict(FeedbackAnalysisSignature)  # type: ignore[attr-defined]
    out = predict(
        student_text_md=text_md,
        criteria=list(criteria),
        teacher_instructions_md=teacher_instructions_md,
        teacher_context_md=teacher_context_md,
    )
    score_value = getattr(out, "overall_score", 0)
    try:
        score_int = int(score_value) if score_value is not None else 0
    except Exception:
        score_int = 0
    return CriteriaAnalysis(
        schema="criteria.v2",
        score=score_int,
        criteria_results=_ensure_criteria_results(getattr(out, "criteria_results", [])),
    )


def run_structured_feedback(
    *,
    text_md: str,
    criteria: Sequence[str],
    analysis_json: CriteriaAnalysis | dict[str, Any],
    teacher_instructions_md: str | None = None,
    teacher_context_md: str | None = None,
) -> str:
    """Execute DSPy Predict(Signature) to obtain feedback prose."""
    try:  # pragma: no cover
        import dspy  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise ImportError(f"dspy unavailable: {exc}")

    payload = analysis_json.to_dict() if isinstance(analysis_json, CriteriaAnalysis) else analysis_json
    predict = dspy.Predict(FeedbackSynthesisSignature)  # type: ignore[attr-defined]
    out = predict(
        student_text_md=text_md,
        analysis_json=payload,
        teacher_instructions_md=teacher_instructions_md,
        teacher_context_md=teacher_context_md,
    )
    val = getattr(out, "feedback_md", None)
    if isinstance(val, str) and val.strip() and val.strip().lower() != "none":
        return val
    raise RuntimeError("empty_feedback_md")


def run_feedback_no_criteria(
    *,
    text_md: str,
    teacher_instructions_md: str | None = None,
    teacher_context_md: str | None = None,
) -> str:
    """Execute DSPy Predict(Signature) to obtain feedback prose without criteria."""
    try:  # pragma: no cover
        import dspy  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise ImportError(f"dspy unavailable: {exc}")

    predict = dspy.Predict(FeedbackNoCriteriaSignature)  # type: ignore[attr-defined]
    out = predict(
        student_text_md=text_md,
        teacher_instructions_md=teacher_instructions_md,
        teacher_context_md=teacher_context_md,
    )
    val = getattr(out, "feedback_md", None)
    if isinstance(val, str) and val.strip() and val.strip().lower() != "none":
        return val
    raise RuntimeError("empty_feedback_md")


def run_structured_visual_analysis(
    *,
    image_data_uri: str,
    criteria: Sequence[str],
    teacher_instructions_md: str | None = None,
    teacher_context_md: str | None = None,
) -> CriteriaAnalysis:
    """Execute DSPy Predict(Signature) to obtain structured analysis from an image."""
    try:  # pragma: no cover - exercised via tests
        import dspy  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise ImportError(f"dspy unavailable: {exc}")

    img = dspy.Image(url=str(image_data_uri))  # type: ignore[attr-defined]
    predict = dspy.Predict(VisualFeedbackAnalysisSignature)  # type: ignore[attr-defined]
    out = predict(
        student_image=img,
        criteria=list(criteria),
        teacher_instructions_md=teacher_instructions_md,
        teacher_context_md=teacher_context_md,
    )
    score_value = getattr(out, "overall_score", 0)
    try:
        score_int = int(score_value) if score_value is not None else 0
    except Exception:
        score_int = 0
    return CriteriaAnalysis(
        schema="criteria.v2",
        score=score_int,
        criteria_results=_ensure_criteria_results(getattr(out, "criteria_results", [])),
    )


def run_structured_visual_feedback(
    *,
    image_data_uri: str,
    criteria: Sequence[str],
    analysis_json: CriteriaAnalysis | dict[str, Any],
    teacher_instructions_md: str | None = None,
    teacher_context_md: str | None = None,
) -> str:
    """Execute DSPy Predict(Signature) to obtain feedback prose from an image."""
    try:  # pragma: no cover
        import dspy  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise ImportError(f"dspy unavailable: {exc}")

    img = dspy.Image(url=str(image_data_uri))  # type: ignore[attr-defined]
    payload = analysis_json.to_dict() if isinstance(analysis_json, CriteriaAnalysis) else analysis_json
    predict = dspy.Predict(VisualFeedbackSynthesisSignature)  # type: ignore[attr-defined]
    out = predict(
        student_image=img,
        analysis_json=payload,
        teacher_instructions_md=teacher_instructions_md,
        teacher_context_md=teacher_context_md,
    )
    val = getattr(out, "feedback_md", None)
    if isinstance(val, str) and val.strip() and val.strip().lower() != "none":
        return val
    raise RuntimeError("empty_feedback_md")


def run_visual_feedback_no_criteria(
    *,
    image_data_uri: str,
    teacher_instructions_md: str | None = None,
    teacher_context_md: str | None = None,
) -> str:
    """Execute DSPy Predict(Signature) to obtain visual feedback prose without criteria."""
    try:  # pragma: no cover
        import dspy  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise ImportError(f"dspy unavailable: {exc}")

    img = dspy.Image(url=str(image_data_uri))  # type: ignore[attr-defined]
    predict = dspy.Predict(VisualFeedbackNoCriteriaSignature)  # type: ignore[attr-defined]
    out = predict(
        student_image=img,
        teacher_instructions_md=teacher_instructions_md,
        teacher_context_md=teacher_context_md,
    )
    val = getattr(out, "feedback_md", None)
    if isinstance(val, str) and val.strip() and val.strip().lower() != "none":
        return val
    raise RuntimeError("empty_feedback_md")


class FeedbackAnalysisProgram:
    """Lightweight runner facade for the legacy single-step analysis prompt."""

    def __init__(self, *, runner: Callable[..., str]):
        self._runner = runner

    def run(
        self,
        *,
        text_md: str,
        criteria: Sequence[str],
        teacher_instructions_md: str | None = None,
        teacher_context_md: str | None = None,
    ) -> str:
        import inspect as _inspect
        kwargs = {"text_md": text_md, "criteria": criteria}
        try:
            sig = _inspect.signature(self._runner)
            if "teacher_instructions_md" in sig.parameters:
                kwargs["teacher_instructions_md"] = teacher_instructions_md
            if "teacher_context_md" in sig.parameters:
                kwargs["teacher_context_md"] = teacher_context_md
        except Exception:
            pass
        return self._runner(**kwargs)


class FeedbackSynthesisProgram:
    """Wrapper around the feedback-synthesis runner (second DSPy stage)."""

    def __init__(self, *, runner: Callable[..., str]):
        self._runner = runner

    def run(
        self,
        *,
        text_md: str,
        criteria: Sequence[str],
        analysis_json: dict[str, Any],
        teacher_instructions_md: str | None = None,
    ) -> str:
        import inspect as _inspect
        kwargs = {"text_md": text_md, "criteria": criteria, "analysis_json": analysis_json}
        try:
            sig = _inspect.signature(self._runner)
            if "teacher_instructions_md" in sig.parameters:
                kwargs["teacher_instructions_md"] = teacher_instructions_md
        except Exception:
            pass
        return self._runner(**kwargs)

```

```python
"""
DSPy vision program (OCR/text extraction).

Intent:
    Provide a callable that the local Vision adapter may use when `dspy` is
    importable, returning extracted Markdown text and lightweight metadata.

Design:
    - DSPy-only: uses `dspy.Predict(Signature)`; LM wiring happens via `dspy.context(...)`.
    - Fail-fast: no deterministic fallback text is generated in Python.
    - No clipping: the caller enforces the 65_536 char limit.
"""

from __future__ import annotations

from backend.learning.adapters.dspy.signatures import VisionOcrSignature


def extract_text_from_image(*, image_data_uri: str) -> tuple[str, dict]:
    """Extract Markdown text from an image via DSPy."""
    try:  # pragma: no cover - exercised via unit tests with stubbed dspy module
        import dspy  # type: ignore

        _ = getattr(dspy, "__version__", None)
    except Exception:
        raise ImportError("dspy is not available")

    img = dspy.Image(url=str(image_data_uri))  # type: ignore[attr-defined]
    predict = dspy.Predict(VisionOcrSignature)  # type: ignore[attr-defined]
    out = predict(student_image=img)
    val = getattr(out, "text_md", None)
    if isinstance(val, str) and val.strip() and val.strip().lower() != "none":
        return val.strip(), {"backend": "dspy", "program": "vision_ocr"}
    raise RuntimeError("empty_ocr_text_md")
```

### Adapter-Level: DSPy-Pipelines (aktuell)
Das sind die aktuellen Orchestrierungs-Entrypoints, die von den Learning-Adaptern verwendet werden:

- `backend/learning/adapters/dspy/feedback_program.py`: `analyze_feedback(...)`
- `backend/learning/adapters/dspy/visual_feedback_program.py`: `analyze_visual_feedback(...)`
- `backend/learning/adapters/dspy/vision_program.py`: `extract_text_from_image(...)`

## Geplante Anpassungen am DSPy Prompt-Vertrag (nächster Schritt)
Wir behalten die Schülerabgabe in beiden Stufen (Analyse und Synthese) als Input, damit das Feedback auf konkrete Teile der Einreichung (Text oder visuelle Inhalte) Bezug nehmen kann.

### 1) Ausgabeformat für Synthese (standardisiert)
Gilt für:
- `FeedbackSynthesisSignature.feedback_md`
- `VisualFeedbackSynthesisSignature.feedback_md`

Vertrag (Prompt-Ebene + minimale Runtime-Validierung):
- Output ist Markdown und enthält die beiden **fettgedruckten** Überschriften:
  1) `**Das ist dir gut gelungen:** ...`
  2) `**Das kannst du besser:** ...`
- Runtime-Validierung: Wenn eine Überschrift fehlt oder `feedback_md` leer ist → **transient error** (retry). Kein „synthetic prose“-Fallback.

Zusätzliche Stil-Empfehlungen (nicht hart validiert; nur Prompt):
- Fließtext statt Listen/Bullets.
- Kurz und classroom-tauglich halten (z.B. 2–4 Sätze pro Absatz).

### 2) Qualität der Analyse-Begründungen (ohne Zitatpflicht)
Gilt für:
- `FeedbackAnalysisSignature.criteria_results[i].explanation_md`
- `VisualFeedbackAnalysisSignature.criteria_results[i].explanation_md`

Vertrag:
- 1–3 kurze Sätze auf Deutsch, die erklären, *warum* der Score so vergeben wurde.
- Verständlich und mit Bezug zur Abgabe, aber **ohne Pflicht zu wörtlichen Zitaten** (Text) und ohne „Beobachtungsprotokoll“ (visuell).
- Wenn kein Beleg gefunden wird: Score `0` und Erklärung „kein Beleg gefunden“.

## Zielverhalten (Fehlersemantik)
### Grundregel
**Jeder Fehlschlag, ein valides DSPy-Ergebnis zu erzeugen, ist ein Fehler und soll Worker-Retries auslösen.**

### Fehlerklassifikation im Worker
Der Worker unterscheidet:
- `FeedbackTransientError` → Retry mit Backoff bis MAX_RETRIES, dann `feedback_failed` markieren.
- `FeedbackPermanentError` → sofort als fehlgeschlagen markieren (kein Retry).
- `VisionTransientError` → Retry mit Backoff bis MAX_RETRIES, dann `vision_failed` markieren.
- `VisionPermanentError` → sofort als fehlgeschlagen markieren (kein Retry).

Zuordnung:
- `dspy` Import fehlt → transient.
- Konfiguration fehlt (Endpoint/Modell) → transient.
- DSPy-Laufzeitfehler (Timeouts, Netzwerk-/Model-Fehler, invalid/leer Output) → transient.
- Nicht unterstützte MIME-Types → permanent.

## BDD-Szenarien (Gegeben–Wenn–Dann)
### Text-Feedback (Task.kind != "visual")
1. **Erfolgsfall**
   - Gegeben `dspy` ist importierbar und konfiguriert
   - Und `OPENAI_BASE_URL` ist gesetzt
   - Und `AI_TEXT_MODEL` ist gesetzt
   - Und Kriterien sind nicht leer
   - Wenn der Worker `FeedbackAdapter.analyze(...)` aufruft
   - Dann liefert das System `FeedbackResult` mit:
     - `analysis_json.schema == "criteria.v2"`
     - nicht-leerem `feedback_md`, das dem Standardformat entspricht:
       - enthält `**Das ist dir gut gelungen:**` und `**Das kannst du besser:**`
   - Und der Adapter ruft nirgendwo `ollama.Client.*` auf.

2. **DSPy fehlt**
   - Gegeben `dspy` Import schlägt fehl
   - Wenn Feedback angefordert wird
   - Dann loggen wir einen klaren Reason-Code (z.B. `dspy_unavailable`)
   - Und werfen `FeedbackTransientError`.

3. **Konfiguration fehlt**
   - Gegeben `dspy` ist importierbar, aber `OPENAI_BASE_URL` oder `AI_TEXT_MODEL` fehlt/ist leer
   - Wenn Feedback angefordert wird
   - Dann loggen wir `missing_endpoint` / `missing_model`
   - Und werfen `FeedbackTransientError`.

4. **Leere Kriterienliste (erlaubt)**
   - Gegeben `criteria=[]`
   - Wenn Feedback angefordert wird
   - Dann liefern wir trotzdem ein nicht-leeres, von DSPy erzeugtes `feedback_md`
   - Und `analysis_json` ist `{}`.

5. **DSPy liefert leeres/None Feedback**
   - Gegeben DSPy läuft, aber liefert kein brauchbares `feedback_md`
   - Wenn Feedback angefordert wird
   - Dann werfen wir `FeedbackTransientError`.

6. **DSPy liefert ungültiges Feedback-Format**
   - Gegeben DSPy liefert `feedback_md`, aber es verletzt das Standardformat (Überschriften fehlen)
   - Wenn Feedback angefordert wird
   - Dann werfen wir `FeedbackTransientError`.

### Visuelles Feedback (Task.kind == "visual")
7. **Erfolgsfall**
   - Gegeben `dspy` ist importierbar und für ein vision-fähiges Modell konfiguriert
   - Und `OPENAI_BASE_URL` ist gesetzt
   - Und `AI_VISUAL_MODEL` ist gesetzt
   - Und die Submission ist image/png|image/jpeg|application/pdf
   - Und Kriterien sind nicht leer
   - Wenn der Worker `FeedbackAdapter.analyze_visual(...)` aufruft
   - Dann liefert das System eine valide `criteria.v2` Analyse und ein nicht-leeres `feedback_md`, das dem Standardformat entspricht.

8. **Leere Kriterienliste (erlaubt)**
   - Gegeben `criteria=[]`
   - Wenn visuelles Feedback angefordert wird
   - Dann liefern wir trotzdem ein nicht-leeres, von DSPy erzeugtes `feedback_md`
   - Und `analysis_json` ist `{}`.

9. **Beliebiger DSPy-Fehler**
   - Gegeben Analyse oder Synthese schlägt fehl
   - Wenn visuelles Feedback angefordert wird
   - Dann werfen wir `FeedbackTransientError`.

10. **Nicht unterstützter MIME-Type**
   - Gegeben ein nicht unterstützter MIME-Type
   - Wenn visuelles Feedback angefordert wird
   - Dann werfen wir `FeedbackPermanentError("unsupported_mime")`.

11. **Konfiguration fehlt**
   - Gegeben `dspy` ist importierbar, aber `OPENAI_BASE_URL` oder `AI_VISUAL_MODEL` fehlt/ist leer
   - Wenn visuelles Feedback angefordert wird
   - Dann loggen wir `missing_endpoint` / `missing_model`
   - Und werfen `FeedbackTransientError`.

12. **DSPy liefert ungültiges Feedback-Format**
   - Gegeben DSPy liefert `feedback_md`, aber es verletzt das Standardformat (Überschriften fehlen)
   - Wenn visuelles Feedback angefordert wird
   - Dann werfen wir `FeedbackTransientError`.

### Vision-Textextraktion („OCR“/Handschrift) (Submission.kind=image|file)
13. **Erfolgsfall**
   - Gegeben `dspy` ist importierbar und für ein vision-fähiges Modell konfiguriert
   - Und `OPENAI_BASE_URL` ist gesetzt
   - Und `AI_OCR_MODEL` ist gesetzt
   - Und die Submission ist image/png|image/jpeg|application/pdf
   - Wenn der Worker `VisionAdapter.extract(...)` aufruft
   - Dann liefert das System `VisionResult` mit nicht-leerem `text_md` (Markdown)
   - Und der Adapter ruft nirgendwo `ollama.Client.*` auf.

14. **DSPy fehlt**
   - Gegeben `dspy` Import schlägt fehl
   - Wenn Vision-Extraktion angefordert wird
   - Dann loggen wir `dspy_unavailable`
   - Und werfen `VisionTransientError`.

15. **Konfiguration fehlt**
   - Gegeben `dspy` ist importierbar, aber `OPENAI_BASE_URL` oder `AI_OCR_MODEL` fehlt/ist leer
   - Wenn Vision-Extraktion angefordert wird
   - Dann loggen wir `missing_endpoint` / `missing_model`
   - Und werfen `VisionTransientError`.

16. **Nicht unterstützter MIME-Type**
   - Gegeben ein nicht unterstützter MIME-Type
   - Wenn Vision-Extraktion angefordert wird
   - Dann werfen wir `VisionPermanentError("unsupported_mime")`.

17. **DSPy liefert leeren/None OCR-Text**
   - Gegeben DSPy läuft, aber liefert keinen brauchbaren Markdown-Text
   - Wenn Vision-Extraktion angefordert wird
   - Dann werfen wir `VisionTransientError`.

18. **OCR-Output zu lang**
   - Gegeben DSPy liefert OCR-Markdown länger als 65_536 Zeichen
   - Wenn Vision-Extraktion angefordert wird
   - Dann werfen wir `VisionTransientError` (retry) mit Reason-Code wie `ocr_text_too_long`.

## Testplan (TDD: Rot → Grün → Refactor)
### Stand (umgesetzt)
Die API-/Adapter-Tests sind auf die neue DSPy-only Semantik umgestellt (kein `ollama`, kein `AI_BACKEND`, kein Fallback-Output).
Wichtige Test-Orte:
- Adapter-/DSPy-Vertrag: `backend/tests/learning_adapters/`
  - Feedback: `test_feedback_program_dspy_structured.py`, `test_local_feedback_dspy.py`
  - Vision/OCR: `test_vision_program_dspy.py`, `test_local_vision.py`
- Worker/DI/Guards: `backend/tests/test_learning_config.py`, `backend/tests/test_learning_worker_di_switch.py`, `backend/tests/test_config_security.py`

### Umsetzungspunkte (erledigt)
- Ein OpenAI-kompatibler Endpoint (`OPENAI_BASE_URL`) + Modellvariablen (`AI_TEXT_MODEL`, `AI_OCR_MODEL`, `AI_VISUAL_MODEL`).
- Vision-OCR via `VisionOcrSignature` + `vision_program.extract_text_from_image(...)` (DSPy-only).
- Kein „synthetic prose“-Fallback: fehlendes/leeres `feedback_md` ist ein Fehler (retry).

### Schritt 3: Refactor für Klarheit (REFACTOR)
- Branching und duplizierte Error-Mappings reduzieren.
- Docstrings so schreiben, dass „why“ und Permissions klar sind.
- Logs PII-frei halten (kein Schülertext, keine Bild-Bytes).

## Verifikation
Empfohlene Befehle (lokal = prod):
- `.venv/bin/pytest -q`
- Optional während der Iteration:
  - `.venv/bin/pytest -q backend/tests/learning_adapters/test_local_feedback_dspy.py`
  - `.venv/bin/pytest -q backend/tests/learning_adapters/test_visual_feedback_program_dspy_structured.py`
  - `.venv/bin/pytest -q backend/tests/learning_adapters/test_local_vision.py`

## Dokumentations-Updates
- `docs/references/LLM-Prompts.md` aktualisieren:
  - Feedback und Vision-Extraktion nutzen nur DSPy Signatures/Module (ein Prompt-Vertrag).
  - Visuelle Tasks nutzen die visuelle DSPy-Pipeline (Bild/PDF → Analyse → Feedback).
- `docs/references/learning_ai.md` aktualisieren:
  - Ollama-spezifische Formulierungen durch OpenAI-kompatiblen Endpoint + Modell-Variablen ersetzen.
  - Privacy-Erwartungen für Betreiber dokumentieren (wo läuft der Endpoint, welche Daten werden gesendet).

## Risiken
- Ohne deterministische Fallbacks führt ein falsch konfigurierter Endpoint/Modell zu Retries und am Ende zu fehlgeschlagenen Submissions.
- Striktere Validierung kann Schwächen bei der Vertragstreue von Modellen sichtbarer machen.
- Beliebige Endpoints zu erlauben ist eine Betreiber-Entscheidung mit Privacy-Implikationen.

Gegenmaßnahmen:
- Starke Observability (strukturierte Logs: nur Reason-Codes, kein Inhalt).
- Klare Runbooks: required ENV, Smoke-Tests für Endpoint und Modelle.
