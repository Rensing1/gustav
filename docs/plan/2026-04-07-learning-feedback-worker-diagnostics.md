# Learning-Feedback: Worker-Diagnose für `feedback_failed`

Status: abgeschlossen

## Ziel

Der Learning Worker soll bei fehlgeschlagenen Feedback-Jobs eine aussagekräftige,
aber weiterhin sichere Fehlerdiagnose liefern.

## Entscheidungen

- Keine Frontend- oder API-Änderung in diesem Schritt.
- Keine Migration: bestehende Fehlerfelder werden präziser genutzt.
- Es werden nur stabile, interne Fehlercodes persistiert und geloggt.
- Unbekannte Provider-/DSPy-Ausnahmen bleiben sanitisiert als `feedback_failed`.

## Umsetzung

- Der lokale Feedbackadapter unterscheidet zusätzlich sichere Fehlergründe wie
  `invalid_feedback_format` und `empty_feedback_md`.
- Der Worker loggt bei Feedbackfehlern neben Klassennamen auch den stabilen
  Fehlergrund und harmlose Kontextdaten (`task_id`, `intent`, `criteria_count`).
- `feedback_last_error` speichert den konkreten sicheren Fehlergrund statt nur
  pauschal `feedback_failed`, sofern dieser bekannt ist.

## Tests

- Adaptertests für sichere Fehlerklassifikation ohne PII-Leak.
- Worker-Tests für präzisere Fehlerpersistenz und Logausgabe.
