# LLM-Prompts in GUSTAV (Learning)

Diese Referenz beschreibt die zentralen Prompt-Verträge, mit denen GUSTAV im Learning-Kontext OCR und formative Rückmeldungen erzeugt.

Grundidee: **Der Prompt-Vertrag lebt ausschließlich in DSPy-Signatures** (Deutsch) und den dazugehörigen DSPy-Programmen. Es gibt keine zweite, parallele Prompt-Quelle (keine Prompt-Templates, keine Ollama-Fallback-Prompts).

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
