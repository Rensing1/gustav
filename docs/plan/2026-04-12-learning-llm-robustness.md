# Plan: Learning LLM-Robustheit für strukturierte Analyse härten

Status: in Arbeit
Datum: 2026-04-12

## Ziel
- Formale Analysefehler aus dem LLM-Ausgabeformat sollen deutlich seltener werden.
- Bild-/PDF-Abgaben im `visual_direct`-Pfad sollen nicht mehr regelmäßig an
  ungültigen strukturierten Analyse-Ausgaben scheitern.
- Der öffentliche Fehlerpfad `feedback_invalid_analysis` bleibt als terminaler
  Endzustand erhalten, wenn auch ein gezielter interner Reparaturversuch
  scheitert.

## Produktentscheidungen
- Die strukturierte Analyse wechselt von frei gewählten `criterion_idx`-Werten
  zu einer positionsgebundenen Ergebnisliste.
- Der Analyse-Call wird prompt- und parameterseitig härter von der
  Rückmeldungssynthese getrennt.
- Bei formal ungültiger Analyse gibt es genau einen internen Reparaturversuch
  im selben Worker-Job.
- Repair-Status bleibt intern; keine neue student- oder teacher-seitige
  API-/UI-Sichtbarkeit in diesem Schritt.

## Contract-First
- `docs/references/LLM-Prompts.md` und die DSPy-Signatures bleiben die
  Prompt-Source-of-Truth und werden synchron umgestellt.
- Öffentliche Submission-Verträge in `api/openapi.yml` bleiben stabil; nur
  interne Analyse-/Telemetry-Semantik ändert sich.

## TDD / Red-Green-Refactor
1. RED
   - Shared-Mapper-Tests für positionsgebundene Analyseergebnisse
   - Text-/Visual-Programmtests für einen einmaligen Reparaturversuch
   - Worker-Test für `visual_direct` mit erst ungültigem, dann repariertem
     Analyseoutput
2. GREEN
   - Signatures und Mapper auf positionsgebundene Ausgabe umstellen
   - Analyse-/Synthese-Parameter trennen
   - Reparaturpfad minimal ergänzen
3. REFACTOR
   - Telemetrie-/Statusbegriffe klein und lesbar kapseln
   - Kommentare nur an nicht offensichtlichen Stellen

## Verifikation
- `backend/tests/learning_adapters/test_dspy_overall_score_derived.py`
- `backend/tests/learning_adapters/test_feedback_program_dspy_structured.py`
- `backend/tests/learning_adapters/test_visual_feedback_program_dspy_structured.py`
- `backend/tests/learning_adapters/test_local_feedback_dspy.py`
- `backend/tests/test_learning_worker_visual_dspy_pipeline.py`
