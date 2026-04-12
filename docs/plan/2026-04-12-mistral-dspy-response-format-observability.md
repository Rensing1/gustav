# Mistral DSPy Response-Format Observability

## Ziel

Für `mistral-small-4` soll GUSTAV den bestehenden DSPy-/LiteLLM-Pfad beibehalten,
aber zwei Lücken schließen:

1. generische `reasoning_effort`-Konfiguration für Analyse und Synthese
2. interne Sichtbarkeit, ob DSPy Structured Outputs (`json_schema`) nutzt oder auf
   `json_object` zurückfällt

## Entscheidungen

- Kein nativer Mistral-SDK-Pfad in dieser Phase
- Keine API- oder DB-Änderung
- Sichtbarkeit nur intern über Logs und interne Telemetrie
- `reasoning_effort` nur für Mistral-Familien aktiv; andere Modelle ignorieren den Wert
- Default für Mistral bleibt konservativ: `reasoning_effort=none`

## Umsetzung

- `backend/learning/adapters/dspy/helpers.py`
  - Mistral-Modellerkennung und `reasoning_effort`-Hilfsfunktionen ergänzen
- `backend/learning/adapters/local_feedback.py`
  - neue ENV-Variablen für Text/Visual Analyse und Synthese einlesen
  - `reasoning_effort` an `dspy.LM(...)` weitergeben
- `backend/learning/adapters/dspy/`
  - instrumentierten JSON-Adapter ergänzen
  - Stage-spezifische Logs für Analyse/Synthese und Visual-Analyse/-Synthese ergänzen
- Doku
  - `.env.example`
  - `docker-compose.yml`
  - `docs/references/learning_ai.md`

## Tests

- Helper-Tests für Mistral-`reasoning_effort`
- Adapter-Tests für ENV-Fallbacks und `dspy.LM(...)`-Kwargs
- JSON-Adapter-Tests für `json_schema`, `json_object_fallback`, `json_object_forced`
- Programmtests für Stage-Logs ohne PII
