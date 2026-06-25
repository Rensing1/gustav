# DSPy-Synthesis analysis_json Type-Mismatch Implementation Plan

Status: umgesetzt
Datum: 2026-06-03

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Behebe die DSPy-Warnungen `Type mismatch for field 'analysis_json'`, ohne den öffentlichen `criteria.v2`-JSON-Vertrag oder die Persistenz in `learning_submissions.analysis_json` zu ändern.

**Architecture:** Die Analyse-Stufe darf intern weiterhin `CriteriaAnalysis` verwenden, aber die Synthesis-Grenze arbeitet mit dem normalisierten JSON-kompatiblen `dict`, das auch OpenAPI, Worker-Port und Datenbank verwenden. Dadurch bleibt `criteria.v2` die gemeinsame Vertragssprache zwischen Analyse, Feedback-Synthesis, API und Postgres `jsonb`.

**Tech Stack:** Python 3.11, pytest, DSPy Signatures, GUSTAV Learning-Worker-Adapter.

---

## Kontext

Das Ticket `docs/tickets/learning-dspy-synthesis-analysis-json-type-mismatch-2026-05-28.md` beschreibt viele nicht-blockierende Produktionswarnungen während eines Unterrichtsfensters am 2026-05-28. Alle Abgaben wurden abgeschlossen, aber DSPy warnte wiederholt, weil die Synthesis-Signatur `analysis_json` als `CriteriaAnalysis` deklariert, während die Pipeline vor dem Synthesis-Aufruf bereits korrekt auf einen JSON-kompatiblen `criteria.v2`-`dict` normalisiert.

Anschaulich: Der Inhalt der Analyse ist richtig, aber das Typetikett an der DSPy-Synthesis-Grenze sagt noch „Python-Objekt“, obwohl dort fachlich „JSON“ übergeben wird.

## User Story und BDD

**User Story:** Als Betreiber von GUSTAV möchte ich, dass gültige `criteria.v2`-Analysen ohne DSPy-Type-Mismatch durch Text- und Visual-Synthesis laufen, damit Produktionslogs echte Probleme sichtbar halten und spätere DSPy-Updates nicht aus einer Warnung einen harten Fehler machen.

- Given eine gültige textbasierte `criteria.v2`-Analyse als `dict`, when die Text-Synthesis aufgerufen wird, then DSPy sieht für `analysis_json` einen kompatiblen Typ.
- Given eine gültige visuelle `criteria.v2`-Analyse als `dict`, when die Visual-Synthesis aufgerufen wird, then DSPy sieht denselben kompatiblen JSON-Vertrag.
- Given die Analyse-Stufe liefert intern ein `CriteriaAnalysis`-Objekt, when `run_structured_feedback(...)` oder `run_structured_visual_feedback(...)` aufgerufen wird, then der Payload bleibt vor DSPy JSON-kompatibel normalisiert.
- Given `analysis_json` wird persistiert, when der Worker `FeedbackResult.analysis_json` speichert, then die gespeicherte Form bleibt ein `criteria.v2`-JSON-Objekt.

## Task 1: Regressionstest für den DSPy-Synthesis-Vertrag

**Files:**
- Create: `backend/tests/learning_adapters/test_dspy_synthesis_analysis_json_type_contract.py`

- [x] Schreibe zuerst einen Test, der einen gültigen `criteria.v2`-Payload als `dict` gegen `FeedbackSynthesisSignature.input_fields["analysis_json"].annotation` prüft.
- [x] Schreibe denselben Test für `VisualFeedbackSynthesisSignature`.
- [x] Run: `.venv/bin/pytest -q backend/tests/learning_adapters/test_dspy_synthesis_analysis_json_type_contract.py`
- [x] Expected before fix: FAIL, weil die Signatur aktuell `CriteriaAnalysis` erwartet und DSPys Typeguard den `dict` ablehnt.

## Task 2: Minimaler Signatur-Fix

**Files:**
- Modify: `backend/learning/adapters/dspy/signatures.py`

- [x] Ändere nur die beiden echten DSPy-Synthesis-InputFields:
  - `FeedbackSynthesisSignature.analysis_json: CriteriaAnalysis` zu `dict[str, Any]`.
  - `VisualFeedbackSynthesisSignature.analysis_json: CriteriaAnalysis` zu `dict[str, Any]`.
- [x] Lasse die Fallback-Dataclasses unverändert, weil sie bereits `dict[str, Any]` verwenden.
- [x] Lasse `programs.py`, `feedback_program.py` und `visual_feedback_program.py` unverändert, weil sie bereits korrekt auf `dict` normalisieren.
- [x] Run: `.venv/bin/pytest -q backend/tests/learning_adapters/test_dspy_synthesis_analysis_json_type_contract.py`
- [x] Expected after fix: PASS.

## Task 3: Regression

**Files:**
- Existing tests only.

- [x] Run: `.venv/bin/pytest -q backend/tests/learning_adapters/test_feedback_program_dspy_structured.py backend/tests/learning_adapters/test_visual_feedback_program_dspy_structured.py backend/tests/learning_adapters/test_dspy_json_observability.py`
- [x] Expected: PASS.

## Umsetzungsergebnis

- `FeedbackSynthesisSignature.analysis_json` und `VisualFeedbackSynthesisSignature.analysis_json` akzeptieren jetzt `dict[str, Any]`.
- Der JSON-kompatible `criteria.v2`-Payload bleibt die gemeinsame Form für Synthesis, Worker-Port, API und Postgres `jsonb`.
- Die Analyse-Dataclass `CriteriaAnalysis` bleibt in `programs.py` weiterhin als internes Hilfsobjekt unterstützt und wird vor der Synthesis mit `to_dict()` normalisiert.

## Verifikation

- Roter Test vor Fix: `.venv/bin/pytest -q backend/tests/learning_adapters/test_dspy_synthesis_analysis_json_type_contract.py` -> 2 fehlgeschlagen wegen `CriteriaAnalysis`-Annotation.
- Grüner Test nach Fix: `.venv/bin/pytest -q backend/tests/learning_adapters/test_dspy_synthesis_analysis_json_type_contract.py` -> 2 bestanden.
- Regression: `.venv/bin/pytest -q backend/tests/learning_adapters/test_feedback_program_dspy_structured.py backend/tests/learning_adapters/test_visual_feedback_program_dspy_structured.py backend/tests/learning_adapters/test_dspy_json_observability.py` -> 12 bestanden.

## Annahmen

- Keine OpenAPI-Änderung nötig: `api/openapi.yml` beschreibt `analysis_json` bereits als strukturiertes JSON.
- Keine Supabase-Migration nötig: `learning_submissions.analysis_json` bleibt `jsonb`.
- `CriteriaAnalysis` bleibt als internes Python-Hilfsobjekt für die Analyse-Stufe sinnvoll; nur die Synthesis-Grenze wird auf den JSON-Vertrag ausgerichtet.
- Neue Tests enthalten keine Schülertexte, Prompts, Tokens oder personenbezogenen Daten.
