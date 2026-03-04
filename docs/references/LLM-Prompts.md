# LLM-Prompts in GUSTAV (Learning)

Diese Referenz beschreibt die zentralen Prompt-Verträge, mit denen GUSTAV im Learning-Kontext OCR und formative Rückmeldungen erzeugt.

Grundidee: **Der Prompt-Vertrag lebt ausschließlich in DSPy-Signatures** (Deutsch) und den dazugehörigen DSPy-Programmen. Es gibt keine zweite, parallele Prompt-Quelle (keine Prompt-Templates, keine Ollama-Fallback-Prompts).

Stand: Working tree (dieses Dokument spiegelt die Signature-Docstrings 1:1 wider; bei Änderungen an den Signatures bitte hier mitziehen).

## 0) Leitplanken
- **Signatures als Contract-Source-of-Truth**: `backend/learning/adapters/dspy/signatures.py`
- **Programme/Orchestrierung**:
  - Text-Feedback: `backend/learning/adapters/dspy/feedback_program.py` + `backend/learning/adapters/dspy/programs.py`
  - Visuelles Feedback: `backend/learning/adapters/dspy/visual_feedback_program.py` + `backend/learning/adapters/dspy/programs.py`
  - OCR: `backend/learning/adapters/dspy/vision_program.py`
- **Fail-fast**: Leere/ungültige Model-Outputs führen zu Fehlern → Worker-Retry. Es gibt keine deterministischen „Fallback-Ausgaben“ im Python-Code.
- **Kein Input-Clipping in Learning AI**:
  - Text-Submissions sind bereits in der HTTP-Schicht auf `<= 65_536` Zeichen limitiert.
  - OCR-Outputs werden ebenfalls auf `<= 65_536` Zeichen begrenzt; größere Outputs führen zu `VisionTransientError("ocr_text_too_long")`.

## 1) Vision/OCR (Bild/PDF → Markdown-Text)

- **Signature**: `VisionOcrSignature` (`backend/learning/adapters/dspy/signatures.py`)
- **Program**: `extract_text_from_image(...)` (`backend/learning/adapters/dspy/vision_program.py`)
- **Adapter**: `backend/learning/adapters/local_vision.py` (DSPy-only)

Semantik:
- Ziel ist **reine Textextraktion** („wie gesehen“), ohne Bewertung/Feedback.
- Output: `text_md` (Markdown), der als Grundlage für die Text-Feedback-Pipeline dient.

## 2) Text-Feedback mit Kriterien (Rubric-Analyse → Rückmeldung)

- **Signatures**:
  - `FeedbackAnalysisSignature` (strukturierte Rubric-Analyse)
  - `FeedbackSynthesisSignature` (Rückmeldung aus Analyse)
- **Programme** (`backend/learning/adapters/dspy/programs.py`):
  - `run_structured_analysis(...)`
  - `run_structured_feedback(...)`
- **Orchestrator**: `analyze_feedback(...)` (`backend/learning/adapters/dspy/feedback_program.py`)

Inputs (konzeptionell):
- `student_text_md` (Schülerabgabe)
- `criteria` (geordnete Kriterienliste)
- `teacher_instructions_md` (Aufgabenstellung; Kontext)
- `teacher_context_md` (Wissensbasis/KI-Kontext; Kontext, teacher-only)

Output:
- `analysis_json` im Schema `criteria.v2` (geordnet, normalisiert)
- `feedback_md` als Markdown-Fließtext (siehe Output-Contract)
Hinweis:
- Der Gesamt-Score `analysis_json.score` (0..5) wird im Backend aus den Kriterien abgeleitet; das Modell liefert nur `criteria_results`.

## 3) Text-Feedback ohne Kriterien (nur Rückmeldung)

Wenn keine Kriterien vorhanden sind (`criteria=[]`), wird die Auswertung übersprungen:
- **Signature**: `FeedbackNoCriteriaSignature`
- **Program**: `run_feedback_no_criteria(...)`
- `analysis_json` ist `{}` und `parse_status="skipped"`.

## 4) Visuelles Feedback (Task.kind == "visual")

Visual Tasks werden **direkt** aus dem visuellen Input bewertet (kein OCR-Zwischenschritt):
- **Signatures**:
  - `VisualFeedbackAnalysisSignature` (strukturierte Analyse aus Bild/PDF)
  - `VisualFeedbackSynthesisSignature` (Rückmeldung aus Analyse)
  - No-criteria: `VisualFeedbackNoCriteriaSignature`
- **Orchestrator**: `analyze_visual_feedback(...)` (`backend/learning/adapters/dspy/visual_feedback_program.py`)
- **Adapter**: `backend/learning/adapters/local_feedback.py` (`analyze_visual(...)`, benötigt `AI_VISUAL_MODEL`)

## 5) Output-Contract (Feedback)

Damit Feedback in der UI konsistent ist, gilt ein harter Format-Check:
- `feedback_md` muss die beiden Überschriften enthalten:
  - `**Das ist dir gut gelungen:**`
  - `**Das kannst du besser:**`
- Wenn eine Überschrift fehlt oder `feedback_md` leer ist → transient error (Worker-Retry).

Hinweis:
- `teacher_context_md` ist teacher-only und wird nicht im Student-DTO ausgegeben. Es dient ausschließlich dazu, Halluzinationen zu reduzieren und Feedback/Auswertung zu verbessern.

## 6) Verbatim Prompt-Texte (DSPy Signature-Docstrings)

Wichtig:
- Die folgenden Abschnitte sind **wörtliche Kopien** der Docstrings aus `backend/learning/adapters/dspy/signatures.py`.
- In DSPy sind diese Docstrings ein zentraler Teil dessen, was wir im Projekt als „Prompt-Vertrag“ verstehen (neben den `InputField`/`OutputField` `desc=`-Texten).

### 6.1) FeedbackAnalysisSignature
Quelle: `backend/learning/adapters/dspy/signatures.py` (`FeedbackAnalysisSignature`)

```text
Analysiere einen Schülertext anhand vorgegebener Kriterien und liefere eine strukturierte Bewertung.

Rolle:
    Du denkst wie eine erfahrene Lehrkraft, die fair und evidenzbasiert korrigiert.

Ziel:
    Für jedes Kriterium soll klar erkennbar sein,
    - wie gut das Kriterium erfüllt ist (Score 0..10) und
    - worauf du dich im Schülertext stützt (kurze Erklärung mit Bezug zur Textstelle).

Regeln (nur evidenzbasiert):
    - Bewerte jedes Kriterium ausschließlich anhand expliziter Informationen im Schülertext.
    - Erfinde keine Inhalte, die nicht im Text stehen.
    - Begründe jede Bewertung sachgerecht und nachvollziehbar.
    - Aufgabenstellung und der lehrkraftseitige KI-Kontext sind nur Kontext: Sie helfen dir zu verstehen,
      worum es in der Aufgabe geht, dürfen aber weder zitiert noch als Begründung verwendet werden.

Skalen:
    - criteria_results[i].score: ganze Zahl von 0 bis 10.
      0 = nicht erfüllt, 5 = teilweise erfüllt, 10 = sehr gut erfüllt.

Ausgabe:
    - `criteria_results`: Liste von Objekten mit
      `criterion_idx` (0-basierter Index in der Eingabeliste `criteria`),
      `score` (0..10) und `explanation_md`.
    - `explanation_md` ist eine kurze, sachliche Erklärung in Markdown
      (1–3 Sätze, auf Deutsch, mit Bezug zum Kriterium und zur Textstelle).
    - Der Server ergänzt anschließend `criterion` (aus `criteria[criterion_idx]`)
      und `max_score=10` für den kanonischen `criteria.v2`-Payload.
```

### 6.2) FeedbackSynthesisSignature
Quelle: `backend/learning/adapters/dspy/signatures.py` (`FeedbackSynthesisSignature`)

```text
Erzeuge aus der Analyse eine kurze, pädagogisch sinnvolle Rückmeldung im Fließtext.

Rolle:
    Du bist eine unterstützende Lehrkraft, die Stärken würdigt und konkrete
    nächste Schritte aufzeigt.

Ziel:
    Aus der strukturierten Analyse (`criteria.v2`) und der Aufgabenstellung soll
    ein gut lesbarer Rückmeldungstext in Markdown entstehen, der
    - zuerst hervorhebt, was gelungen ist, und
    - danach konkret beschreibt, was der Schüler verbessern kann.

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
      den Schüler richtet und zum Weiterarbeiten motiviert.
```

### 6.3) FeedbackNoCriteriaSignature
Quelle: `backend/learning/adapters/dspy/signatures.py` (`FeedbackNoCriteriaSignature`)

```text
Rolle:
    Du bist eine unterstützende Lehrkraft, die Stärken würdigt und konkrete
    nächste Schritte aufzeigt.

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
    Begründe jede Bewertung sachgerecht und nachvollziehbar.
    - Aufgabenstellung und KI-Kontext sind nur Kontext und dürfen nicht zitiert werden.
```

### 6.4) VisualFeedbackAnalysisSignature
Quelle: `backend/learning/adapters/dspy/signatures.py` (`VisualFeedbackAnalysisSignature`)

```text
Analysiere eine visuelle Schülerabgabe (Bild/PDF) evidenzbasiert anhand vorgegebener Kriterien.

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
    - Begründe jede Bewertung sachgerecht und nachvollziehbar.
    - Aufgabenstellung und der lehrkraftseitige KI-Kontext sind nur Kontext; sie dürfen
      nicht als „Beleg“ herangezogen oder zitiert werden.

Ausgabe:
    - `criteria_results`: Liste von {criterion_idx, score 0..10, explanation_md}.
    - Der Server ergänzt anschließend `criterion` (aus `criteria[criterion_idx]`)
      und `max_score=10` für den kanonischen `criteria.v2`-Payload.
```

### 6.5) VisualFeedbackSynthesisSignature
Quelle: `backend/learning/adapters/dspy/signatures.py` (`VisualFeedbackSynthesisSignature`)

```text
Erzeuge aus visueller Analyse eine kurze Rückmeldung im Fließtext.

Rolle:
    Du bist eine unterstützende Lehrkraft, die Stärken würdigt und konkrete
    nächste Schritte aufzeigt.

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
```

### 6.6) VisualFeedbackNoCriteriaSignature
Quelle: `backend/learning/adapters/dspy/signatures.py` (`VisualFeedbackNoCriteriaSignature`)

```text
Erzeuge visuelles Feedback ohne Kriterienliste.

Rolle:
    Du denkst wie eine erfahrene Lehrkraft, die fair und evidenzbasiert korrigiert.

Regeln:
    - Schreibe genau zwei Absätze mit diesen Überschriften (Markdown, fett):
      (1) `**Das ist dir gut gelungen:** ...`
      (2) `**Das kannst du besser:** ...`
    - Keine Listen/Bullets.
    - Erfinde keine Inhalte; beziehe dich nur auf sichtbare Inhalte im Bild/PDF.
    - Aufgabenstellung und KI-Kontext sind nur Kontext und dürfen nicht zitiert werden.
```

### 6.7) VisionOcrSignature
Quelle: `backend/learning/adapters/dspy/signatures.py` (`VisionOcrSignature`)

```text
Extrahiere Text aus einer visuellen Schülerabgabe (OCR/Handschrift/Diagramme) als Markdown.

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
```

## 7) Modellaufrufe (wie DSPy tatsächlich gerufen wird)

Dieser Abschnitt beschreibt die konkreten Aufruf-Muster (ohne die vollständigen Adapter-Implementierungen zu duplizieren).

### 7.1) LM-Konfiguration (OpenAI-kompatibles Endpoint)

Text- und Visual-Feedback werden über `dspy.LM(...)` konfiguriert:
- Quelle: `backend/learning/adapters/local_feedback.py` (`_LocalFeedbackAdapter._get_text_lm`, `_get_visual_lm`)
- Modellnamen: aus `AI_TEXT_MODEL` / `AI_VISUAL_MODEL` (normalisiert zu `openai/<name>` wenn kein Provider-Präfix gesetzt ist)
- Endpoint: `OPENAI_BASE_URL`
- Key: `OPENAI_API_KEY` (Default: `sk-noop`)
- Temperature: `AI_TEXT_TEMPERATURE` / `AI_VISUAL_TEMPERATURE` (Default: `0.0`)
- Fail-fast Config: fehlendes `OPENAI_BASE_URL` → transient error; fehlendes `AI_TEXT_MODEL` → transient error; fehlendes `AI_VISUAL_MODEL` → permanent error.
- Prod-Safety: in prod/stage wird `OPENAI_BASE_URL` gegen unsichere HTTP-Hosts validiert (fail-fast in den Adaptern).

OCR läuft analog:
- Quelle: `backend/learning/adapters/local_vision.py` (`_LocalVisionAdapter._get_ocr_lm`)
- Modellname: aus `AI_OCR_MODEL` (normalisiert zu `openai/<name>` wenn kein Provider-Präfix gesetzt ist)
- Temperature: `AI_OCR_TEMPERATURE` (Default: `0.0`)
- Fail-fast Config: fehlendes `OPENAI_BASE_URL` oder `AI_OCR_MODEL` → transient error.

### 7.2) DSPy Context + Predict(Signature)

Alle drei Pipelines laufen unter einem expliziten DSPy-Kontext:
- `adapter=dspy.JSONAdapter()` (wir erwarten strukturierte Outputs für Analyse/Feedback/OCR)
- `disable_history=True` (kein Chat-History-Drift zwischen Aufrufen)

Beispiele (schematisch, entspricht dem Code):

```python
with dspy.context(lm=lm, adapter=dspy.JSONAdapter(), disable_history=True):
    # Text-Feedback (2-stufig: Analyse → Synthese)
    result = feedback_program.analyze_feedback(
        text_md=text_md,
        criteria=criteria,
        teacher_instructions_md=instruction_md,
        teacher_context_md=teacher_context_md,
    )

with dspy.context(lm=lm, adapter=dspy.JSONAdapter(), disable_history=True):
    # Visuelles Feedback (direkt aus Bild/PDF)
    result = visual_feedback_program.analyze_visual_feedback(
        image_data_uri=image_data_uri,
        criteria=criteria,
        teacher_instructions_md=instruction_md,
        teacher_context_md=teacher_context_md,
    )

with dspy.context(lm=lm, adapter=dspy.JSONAdapter(), disable_history=True):
    # OCR (Bild/PDF -> Markdown)
    text_md, meta = vision_program.extract_text_from_image(image_data_uri=image_data_uri)
```

Zusätzlich (wichtig für das Verständnis der „Prompt-Form“): die eigentlichen Modellaufrufe erfolgen über `dspy.Predict(Signature)` in `backend/learning/adapters/dspy/programs.py`, z.B.:

```python
predict = dspy.Predict(FeedbackAnalysisSignature)
out = predict(
    student_text_md=text_md,
    criteria=list(criteria),
    teacher_instructions_md=teacher_instructions_md,
    teacher_context_md=teacher_context_md,
)

predict = dspy.Predict(FeedbackSynthesisSignature)
out = predict(
    student_text_md=text_md,
    analysis_json=analysis_json,  # dict/CriteriaAnalysis.to_dict()
    teacher_instructions_md=teacher_instructions_md,
    teacher_context_md=teacher_context_md,
)
```
