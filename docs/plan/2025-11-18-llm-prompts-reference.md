## Datum
2025-11-18

## Kontext
GUSTAV nutzt mehrere LLM-Pipelines zur Auswertung von Schülerlösungen:
- Visuelle Analyse / OCR von Datei-Einreichungen (insbesondere Bilder und PDFs mit Handschrift).
- Kriterienbasierte Analyse des transkribierten Textes (criteria.v2).
- Generierung von pädagogischem Feedback aus der strukturierten Analyse.

Die Prompts dafür sind bereits im Code implementiert (Vision-Adapter, DSPy-Feedback-Programm, Ollama-Fallback). Ziel dieses Plans ist es, diese Prompts und ihre Implementierungsstellen in einer eigenständigen Referenzdokumentation festzuhalten.

## Ziel
- Neue Referenzdatei `docs/references/LLM-Prompts.md` anlegen.
- Die drei zentralen Prompt-Arten (Vision/OCR, Analyse, Feedback) inklusive ihrer Implementierungen im Backend dokumentieren.
- Bezug zu den bestehenden Architektur-/AI-Dokumenten herstellen, ohne das Laufzeitverhalten zu ändern.

## Nicht-Ziele
- Keine Änderungen an API-Verträgen (`api/openapi.yml`).
- Keine Änderungen an Datenbank-Schema oder Migrationen.
- Keine Anpassung der eigentlichen Prompt-Texte oder der LM-Aufrufe.

## Schritte
1. Bestehende Implementierungen der Prompts im Backend identifizieren (local_vision, dspy feedback_program, local_feedback).
2. Struktur für `docs/references/LLM-Prompts.md` entwerfen (z. B. Überblick, Pipelines, einzelne Prompts mit Code-Verweisen).
3. Die Referenzdatei erstellen und mit den relevanten Pfaden, kurzen Beschreibungen und Hinweisen zur pädagogischen Zielsetzung der Prompts füllen.

