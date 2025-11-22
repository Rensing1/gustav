# Ticket: GPT-OSS Thinking-Level erzwingen

## Problem
- GPT-OSS akzeptiert nur `think` = `low|medium|high`. `true/false` wird ignoriert, Default liefert längere Traces (siehe https://docs.ollama.com/capabilities/thinking).
- DSPy-/Ollama-Aufrufe im Learning-Worker setzen nirgendwo `think`, daher wird GPT-OSS immer ohne Level angesteuert.

## Aktueller Flow
- Worker-Bootstrap (`backend/learning/workers/process_learning_submission_jobs.py:802ff`): `dspy.LM(f"ollama/{AI_FEEDBACK_MODEL}", api_base=OLLAMA_BASE_URL)` ohne `think`.
- DSPy-Programm (`backend/learning/adapters/dspy/feedback_program.py:~417ff`): erneutes `dspy.configure(...)` ohne `think`.
- Fallback-Ollama (`backend/learning/adapters/local_feedback.py:~140ff`): `client.generate(..., options={...})` ohne `think`.

## Erwartung
- Für GPT-OSS-Modelle muss `think` auf `low` (oder konfigurierbar) gesetzt werden, sonst entsteht unnötig lange Reasoning-Trace.

## Vorschlag
1) Beim LM-Bau in DSPy `extra_body={"think": "low"}` setzen, sobald `AI_FEEDBACK_MODEL` auf GPT-OSS zeigt (String-Check). Sowohl im Worker-Bootstrap als auch im DSPy-Programm.
2) Fallback-Ollama-Aufruf um `options={"think": "low", ...}` ergänzen (nur für GPT-OSS).
3) Optional: Env `AI_THINK_LEVEL` mit Default `low` nur für GPT-OSS-Modelle, um Level per Config zu ändern.

## Risiko/Scope
- Nur Modelle mit Prefix `gpt-oss` betroffen; andere Modelle bleiben unverändert.
- Keine Vertragsänderung nach außen, nur Request-Body-Ergänzung.
