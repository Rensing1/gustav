# Plan: GPT-OSS Think-Level auf "low" erzwingen

## User Story
Als Learning-Worker möchte ich bei GPT-OSS-Modellen den Think-Level explizit auf "low" setzen, damit die Reasoning-Traces kurz bleiben und Feedback-Jobs schneller und ressourcenschonender laufen.

## Annahmen / Nicht-Ziele
- Keine API-Vertragsänderung nötig (nur interne LLM-Konfiguration).
- Schema / Migration: keine Änderungen.
- Gilt nur für GPT-OSS-Modelle; andere Modelle bleiben unverändert.
- Think-Level per Env konfigurierbar (`AI_THINK_LEVEL`, Default `low`), wird aber nur angewendet, wenn das Modellpräfix `gpt-oss` ist.

## BDD-Szenarien (Given-When-Then)
1) Happy Path DSPy LM
   - Given `AI_FEEDBACK_MODEL="gpt-oss"` und `AI_THINK_LEVEL` nicht gesetzt (Default)
   - When der Worker DSPy via `dspy.LM` konfiguriert
   - Then das LM erhält `extra_body={"think": "low"}` und nutzt `api_base` aus `OLLAMA_BASE_URL`.
2) DSPy anderer Modellname
   - Given `AI_FEEDBACK_MODEL="llama3.1"`
   - When der Worker DSPy konfiguriert
   - Then kein `think`-Feld wird gesetzt.
3) DSPy Programm-Pfad (feedback_program)
   - Given `AI_FEEDBACK_MODEL="gpt-oss"`
   - When das DSPy-Programm `dspy.configure` aufruft
   - Then es übergibt das gleiche `extra_body` mit `think="low"`.
4) Ollama-Fallback GPT-OSS
   - Given DSPy fällt aus und Fallback ruft `client.generate`
   - And Modell `gpt-oss`
   - Then der Request setzt `think="low"` (Top-Level-Feld), zusätzlich zu bestehenden Optionen (timeout, raw, template).
5) Ollama-Fallback anderes Modell
   - Given Modell `llama3.1`
   - Then kein `think`-Feld wird gesendet.

## API/OpenAPI
- Keine Änderungen erforderlich (rein interne Modell-Optionssteuerung).

## Migrationen
- Keine Schemaänderungen erforderlich.

## Tests (TDD Red)
- Pytest-Checks für:
  - DSPy LM-Bau im Worker: bei `gpt-oss` wird `think="low"` gesetzt, bei anderen nicht.
  - DSPy feedback_program: `extra_body` enthält `think` für GPT-OSS.
  - Ollama-Fallback: `think` Top-Level-Feld nur bei GPT-OSS gesetzt.

## Umsetzungsschritte (Green)
1) Hilfsfunktion bauen: Think-Level aus Env (`AI_THINK_LEVEL`, Default `low`), nur anwenden bei Modellpräfix `gpt-oss`.
2) Worker-Bootstrap (`process_learning_submission_jobs.py`): `dspy.LM(..., extra_body=...)` ergänzen.
3) DSPy-Programm (`adapters/dspy/feedback_program.py`): gleiches `extra_body` verwenden.
4) Ollama-Fallback (`adapters/local_feedback.py`): `think` Top-Level-Feld konditional setzen.

## Risiken / Checks
- Regression vermeiden: andere Modelle dürfen keine neuen Optionen erhalten.
- Kompatibilität: Ollama-Client akzeptiert `think` als Top-Level; nicht in `options` ablegen.
- Timeout/Template-Optionen dürfen unverändert bleiben.
