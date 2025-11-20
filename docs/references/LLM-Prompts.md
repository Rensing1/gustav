# LLM-Prompts in GUSTAV

Diese Referenz beschreibt die zentralen Prompts, mit denen GUSTAV lokale LLMs zur Auswertung von Schülerlösungen einsetzt. Sie ergänzt die Hintergrunddokumente in `docs/references/learning_ai.md` und `docs/research/feedback_science.md` um konkrete Implementierungsstellen im Code.

Aktuell gibt es drei funktional getrennte Prompt-Arten (mit klarer DSPy-Abgrenzung):

1. Visuelle Analyse von Datei-Einreichungen (OCR/Handschrift-Transkription).
2. Kriteriengeleitete Auswertung der transkribierten Schülerantwort (DSPy-Signatures/Modules).
3. Generierung von pädagogischem Feedback aus der Analyse (DSPy-Signatures/Modules) mit einem klar getrennten lokalen Fallback im Adapter.

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

Die eigentliche inhaltliche Bewertung erfolgt in einer strukturierten Analyse, die das Ergebnis der OCR bzw. Texteingabe nutzt. In der aktuellen Architektur wird dieser Schritt ausschließlich über DSPy-Signatures und -Modules orchestriert; das frühere direkte Prompt-Building im Feedback-Programm wurde entfernt. Die hier dokumentierten Prompts beschreiben daher vor allem das inhaltliche „Contract-Design“, nicht mehr jeden Low-Level-String.

### 2.1 Analyse-Prompt (criteria.v2)

Zweck:

- Aus Schülertext, Kriterienliste und optionalen Lehrkraftinstruktionen eine strukturierte Bewertung im Schema `criteria.v2` erzeugen (Scores + kurze Begründungen).

Implementierung:

- Inhaltlicher Vertrag (Felder, Regeln) kodiert in `backend/learning/adapters/dspy/signatures.py:18` (`FeedbackAnalysisSignature`).
- Structured Execution über `backend/learning/adapters/dspy/programs.py:21` (`run_structured_analysis`).
- Für Dokumentationszwecke ist der frühere String-Prompt weiterhin in `_build_analysis_prompt(...)` (`feedback_program.py`) sichtbar, wird aber nicht mehr direkt gegen das LM geschickt; er dient als „lesbare“ Beschreibung dessen, was die Signature abbilden soll.

Die Analyse-Signature und der entsprechende Prompt-Entwurf enthalten unter anderem folgende Instruktionen:

- Rolle: „Lehrkraft“ mit Auftrag zur Kriterien-Analyse.
- Datenschutz: Ausdrücklicher Hinweis, nur Analysewerte und Begründungen auszugeben, nicht den Schülertext erneut.
- Output-Format: „Striktes JSON im Schema 'criteria.v2' mit 'criteria_results' (Objekte mit criterion, max_score=10, score 0..10, explanation_md).“
- Kontext:
  - Liste der Kriterien (Reihenfolge soll beibehalten werden).
  - Optional: Aufgabenstellung (`teacher_instructions_md`) und Lösungshinweise (`solution_hints_md`).
  - Schülertext („Schülertext (wörtlich): …“).

Die ursprüngliche Prompt-Fassung endete mit der Vorgabe, ausschließlich JSON ohne Prosa zurückzugeben. In der DSPy-Variante wird dieses Verhalten durch die Kombination aus Signature-Feldern und dem `JSONAdapter` erzwungen; `_parse_to_v2(...)` bleibt dennoch als Sicherheitsnetz erhalten, falls ein Modell leicht abweichende Feldnamen oder Werte produziert.

### 2.2 Ausführung der Analyse (DSPy-only)

- Aufruf: `backend/learning/adapters/dspy/programs.run_structured_analysis(...)` erzeugt ein `CriteriaAnalysis`-Objekt über `dspy.Predict(FeedbackAnalysisSignature)`.
- Sicherheitsaspekt: Das Ergebnis wird über `CriteriaAnalysis.to_dict()` in ein flaches JSON überführt und anschließend durch `_parse_to_v2(...)` normalisiert:
  - Feldvarianten (`name` vs. `criterion`, `max` vs. `max_score`) werden vereinheitlicht.
  - Scores werden pro Kriterium und für den Gesamtscore in gültige Bereiche geclamped.
  - Fehlende Kriterien werden deterministisch mit Score 0 ergänzt.
  - Falls die Antwort nicht als JSON parsebar ist, liefert `_parse_to_v2(...)` `None`, und das Feedback-Programm erzeugt ein deterministisches Default-`criteria.v2`-Objekt.

## 3. Pädagogische Feedback-Prompts

Aus der strukturierten Analyse erzeugt GUSTAV eine für Schüler:innen lesbare Rückmeldung.

### 3.1 DSPy-Feedback-Prompt (Rückmeldung aus Analyse)

Zweck:

- Aus `analysis_json` (criteria.v2), Kriterienliste und Kontext eine kurze, gut lesbare Rückmeldung im Fließtext erzeugen.

Implementierung:

- Inhaltlicher Vertrag (Eingaben/Ausgabe) kodiert in `backend/learning/adapters/dspy/signatures.py:45` (`FeedbackSynthesisSignature`).
- Structured Execution über `backend/learning/adapters/dspy/programs.py:40` (`run_structured_feedback`).
- `_build_feedback_prompt(...)` in `feedback_program.py` dokumentiert weiterhin die gewünschte „Lehrkraft-Stimme“ und Struktur, wird aber in der DSPy-Pipeline nicht mehr direkt als Prompt an Ollama übergeben.

Zentrale Elemente der Feedback-Signature / des Prompt-Entwurfs:

- Rolle: „Lehrkraft“, die eine kurze, gut lesbare Rückmeldung formuliert.
- Regeln:
  - Stärken und Verbesserungsmöglichkeiten kurz benennen.
  - Zusammenhängende Sätze, explizit keine Listen/Bullets.
  - Schülertext nicht vollständig wiederholen, sondern Bezug auf die analysierten Kriterien nehmen.
- Kontext:
  - Zusammenfassung der Kriterienergebnisse (`criteria_results`) als Liste mit `criterion`, `score` und `max_score`.
  - Optional: Aufgabenstellung als Kontext (`teacher_instructions_md`).
  - Schülertext („Schülertext (wörtlich): …“).

- Output-Vorgabe: Rückgabe eines einzigen Feldes `feedback_md` als Markdown-Fließtext (keine Listen/Bullets).

In der DSPy-only Architektur wird dieser Contract durch die Signature gesteuert; der eigentliche LLM-Aufruf läuft über `dspy.LM(...)` und `dspy.Predict(...)`, nicht mehr über `_lm_call(...)`.

### 3.2 Ollama-Fallback-Prompt im lokalen Adapter (vereinfachtes Feedback)

Falls der DSPy-Weg (Analyse + Feedback) gar nicht zur Verfügung steht (z.B. DSPy nicht installiert oder env nicht gesetzt), gibt es im lokalen Adapter einen deutlich vereinfachten Rückfall-Prompt.

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
- Verhalten:
  - Das Modelloutput wird nach Möglichkeit als String extrahiert.
  - Wenn keine verwertbare Antwort vorliegt, erzeugt der Adapter eine deterministische Standard-Rückmeldung (Markdown mit „Stärken“ und „Hinweisen“) und ein triviales `criteria.v2`-Objekt (alle Scores = 0).
  - Dieser Fallback wird nur genutzt, wenn DSPy nicht verfügbar oder ausdrücklich übersprungen wird; im DSPy-Pfad selbst gibt es keine direkten Ollama-Prompt-Aufrufe mehr.

## 4. Zusammenfassung der Prompt-Pipeline

End-to-End durchläuft eine Datei-Einreichung typischerweise folgende Prompt-Stufen:

1. **Vision/OCR-Prompt** (`local_vision.py`): Extrahiert den sichtbaren Text aus Bild/PDF in Markdown, ohne Bewertung.
2. **Analyse (DSPy)** (`signatures.py` + `programs.py` + `_parse_to_v2`): Bewertet den Text anhand einer Kriterienliste und liefert strukturierte JSON-Ausgabe im `criteria.v2`-Schema.
3. **Feedback (DSPy)** (`signatures.py` + `programs.py`): Formuliert aus Analyse und Kontext eine pädagogische Rückmeldung in Markdown-Fließtext.
4. **Fallback im lokalen Adapter** (`local_feedback.py`): Greift nur dann auf einen einfachen Ollama-Prompt zurück, wenn DSPy nicht verfügbar ist; im Erfolgsfall liefert auch dieser Pfad ein `criteria.v2`-Objekt und eine Rückmeldung.

Diese klare Trennung unterstützt:

- Datenschutz (Vision/Analyse/Feedback sind entkoppelt, es gibt keine „freien“ Prompt-Ketten mit sensiblen Daten).
- Nachvollziehbarkeit für Lehrkräfte und Entwickler:innen (jede Stufe hat einen klaren Auftrag und ein definiertes Output-Format).
- Didaktische Feintuning-Möglichkeiten: Anpassungen an Rolle, Tonfall oder Struktur können gezielt in der jeweiligen Prompt-Funktion vorgenommen und in diesem Dokument nachvollzogen werden.
