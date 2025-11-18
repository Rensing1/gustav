# LLM-Prompts in GUSTAV

Diese Referenz beschreibt die zentralen Prompts, mit denen GUSTAV lokale LLMs zur Auswertung von Schülerlösungen einsetzt. Sie ergänzt die Hintergrunddokumente in `docs/references/learning_ai.md` und `docs/research/feedback_science.md` um konkrete Implementierungsstellen im Code.

Aktuell gibt es drei funktional getrennte Prompt-Arten:

1. Visuelle Analyse von Datei-Einreichungen (OCR/Handschrift-Transkription).
2. Kriteriengeleitete Auswertung der transkribierten Schülerantwort.
3. Generierung von pädagogischem Feedback aus der Analyse.

## 1. Visuelle Analyse / OCR-Prompt

- Zweck: Aus Bildern und PDFs (inkl. Handschrift-Scans) den sichtbaren Text extrahieren, ohne Interpretation oder Bewertung.
- Implementierung: `backend/learning/adapters/local_vision.py:810`

Der Vision-Adapter baut dort den Prompt:

```python
prompt = (
    "Transcribe the exact visible text as Markdown.\n"
    "- Verbatim OCR: do not summarize or invent structure.\n"
    "- No placeholders, no fabrications, no disclaimers.\n"
    "- Preserve line breaks; omit decorative headers/footers.\n\n"
    f"Input kind: {kind or 'unknown'}; mime: {mime or 'n/a'}.\n"
    "If the content is an image or a scanned PDF page, return only the text you can read."
)
```

- Aufruf: Der Prompt wird zusammen mit den Bilddaten (`image_b64` bzw. `image_list_b64`) an `_call_model(...)` übergeben. Das Ergebnis wird als `VisionResult.text_md` an die nachfolgenden Lern-Use-Cases weitergereicht.
- Pädagogischer Fokus: Die visuelle Stufe soll ausschließlich den Text „wie gesehen“ liefern, ohne Korrekturen oder Feedback – sie dient als technische Grundlage für die spätere didaktische Bewertung.

## 2. Kriteriengeleitete Analyse-Prompts

Die eigentliche inhaltliche Bewertung erfolgt in einer strukturierten Analyse, die das Ergebnis der OCR bzw. Texteingabe nutzt. Diese Prompts sind im DSPy-Feedback-Programm definiert.

### 2.1 Analyse-Prompt (criteria.v2)

- Zweck: Aus Schülertext, Kriterienliste und optionalen Lehrkraftinstruktionen eine strukturierte Bewertung im Schema `criteria.v2` erzeugen (Scores + kurze Begründungen).
- Implementierung: `backend/learning/adapters/dspy/feedback_program.py:93` in `_build_analysis_prompt(...)`

Die Funktion baut einen zusammengesetzten Prompt, unter anderem mit folgenden Instruktionen:

- Rolle: „Lehrkraft“ mit Auftrag zur Kriterien-Analyse.
- Datenschutz: Ausdrücklicher Hinweis, nur Analysewerte und Begründungen auszugeben, nicht den Schülertext erneut.
- Output-Format: „Striktes JSON im Schema 'criteria.v2' mit 'criteria_results' (Objekte mit criterion, max_score=10, score 0..10, explanation_md).“
- Kontext:
  - Liste der Kriterien (Reihenfolge soll beibehalten werden).
  - Optional: Aufgabenstellung (`teacher_instructions_md`) und Lösungshinweise (`solution_hints_md`).
  - Schülertext („Schülertext (wörtlich): …“).

Der Prompt endet mit der Vorgabe, ausschließlich JSON ohne Prosa zurückzugeben. Der resultierende Text wird später in `_parse_to_v2(...)` in dasselbe `criteria.v2`-Schema normalisiert.

### 2.2 Ausführung des Analyse-Prompts

- Aufruf: `_run_model(...)` bzw. `_run_analysis_model(...)` (in derselben Datei) bauen den Prompt über `_build_analysis_prompt(...)` und rufen anschließend `_lm_call(...)` mit diesem Prompt auf.
- Sicherheitsaspekt: Durch das strikte JSON-Format und die Normalisierung in `_parse_to_v2(...)` werden Outputs begrenzt und überprüft, bevor sie in weitere Lernprozesse einfließen.

## 3. Pädagogische Feedback-Prompts

Aus der strukturierten Analyse erzeugt GUSTAV eine für Schüler:innen lesbare Rückmeldung.

### 3.1 DSPy-Feedback-Prompt (Rückmeldung aus Analyse)

- Zweck: Aus `analysis_json` (criteria.v2), Kriterienliste und Kontext eine kurze, gut lesbare Rückmeldung im Fließtext erzeugen.
- Implementierung: `backend/learning/adapters/dspy/feedback_program.py:124` in `_build_feedback_prompt(...)`

Zentrale Elemente des Prompts:

- Rolle: „Lehrkraft“, die eine kurze, gut lesbare Rückmeldung formuliert.
- Regeln:
  - Stärken und Verbesserungsmöglichkeiten kurz benennen.
  - Zusammenhängende Sätze, explizit keine Listen/Bullets.
  - Schülertext nicht vollständig wiederholen, sondern Bezug auf die analysierten Kriterien nehmen.
- Kontext:
  - Zusammenfassung der Kriterienergebnisse (`criteria_results`) als Liste mit `criterion`, `score` und `max_score`.
  - Optional: Aufgabenstellung als Kontext (`teacher_instructions_md`).
  - Schülertext („Schülertext (wörtlich): …“).
- Output-Vorgabe: „Gib ausschließlich den Rückmeldungstext in Markdown (Fließtext) zurück.“

Der Prompt wird in `_run_feedback_model(...)` verwendet, das anschließend `_lm_call(...)` mit diesem Prompt und den konfigurierten LM-Parametern aufruft.

### 3.2 Ollama-Fallback-Prompt (vereinfachtes Feedback)

Falls der DSPy-Weg (Analyse + Feedback) scheitert, gibt es einen deutlich vereinfachten Rückfall-Prompt.

- Zweck: Eine robuste, minimalistische Rückmeldung generieren, falls die strukturierte Pipeline nicht zur Verfügung steht.
- Implementierung: `backend/learning/adapters/local_feedback.py:197`–`201`

Prompt-Inhalt:

```python
prompt = (
    "Provide short formative feedback in Markdown and consider given criteria.\n"
    f"Criteria count: {len(list(criteria))}."
)
```

- Aufruf: Dieser Prompt wird direkt an `ollama.Client.generate(...)` übergeben, mit `options={"raw": True, "template": "{{ .Prompt }}"}` um serverseitige Templates zu umgehen.
- Verhalten: Das Modelloutput wird nach Möglichkeit als String extrahiert; wenn keine verwertbare Antwort vorliegt, erzeugt der Adapter eine deterministische Standard-Rückmeldung (Markdown mit „Stärken“ und „Hinweisen“).

## 4. Zusammenfassung der Prompt-Pipeline

End-to-End durchläuft eine Datei-Einreichung typischerweise folgende Prompt-Stufen:

1. **Vision/OCR-Prompt** (`local_vision.py`): Extrahiert den sichtbaren Text aus Bild/PDF in Markdown, ohne Bewertung.
2. **Analyse-Prompt** (`feedback_program.py`, `_build_analysis_prompt`): Bewertet den Text anhand einer Kriterienliste und liefert strukturierte JSON-Ausgabe im `criteria.v2`-Schema.
3. **Feedback-Prompt** (`feedback_program.py`, `_build_feedback_prompt` bzw. Ollama-Fallback in `local_feedback.py`): Formuliert aus Analyse und Kontext eine pädagogische Rückmeldung in Markdown-Fließtext.

Diese klare Trennung unterstützt:

- Datenschutz (Vision/Analyse/Feedback sind entkoppelt, es gibt keine „freien“ Prompt-Ketten mit sensiblen Daten).
- Nachvollziehbarkeit für Lehrkräfte und Entwickler:innen (jede Stufe hat einen klaren Auftrag und ein definiertes Output-Format).
- Didaktische Feintuning-Möglichkeiten: Anpassungen an Rolle, Tonfall oder Struktur können gezielt in der jeweiligen Prompt-Funktion vorgenommen und in diesem Dokument nachvollzogen werden.

