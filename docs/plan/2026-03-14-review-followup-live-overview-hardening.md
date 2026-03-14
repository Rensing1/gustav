# Plan: Review Follow-up fuer Live Overview Hardening

Status: in Arbeit
Datum: 2026-03-14

## Ziel
Die kleinen Review-Feststellungen sollen ohne Umbau behoben werden:

- deterministische Feedback-Parsefehler robuster als `feedback_invalid_analysis` klassifizieren
- HTMX-Submit-Fehler so behandeln, dass derselbe Idempotency-Key fuer echte Retries erhalten bleibt
- API-Vertrag der Schueler-Live-Filterung an das bereits implementierte `unit_ids=`-Leersignal angleichen

## Warum
- Der Feedback-Adapter soll bei stabilen Strukturfehlern nicht unnoetig retryn.
- Ein verlorener HTMX-Request darf nicht vorzeitig einen neuen Idempotency-Key erzeugen, sonst entstehen Duplikate.
- Der OpenAPI-Vertrag soll die reale Filtersemantik dokumentieren, damit SSR und API konsistent beschrieben sind.

## Umsetzung
1. Regressionstests fuer:
   - `invalid_analysis_json` im Feedback-Adapter
   - HTMX-Fehlerpfad mit erhaltenem `idempotency_key`
   - OpenAPI-Vertrag fuer explizit leere `unit_ids`-Filterung
2. Minimale Codeanpassungen in:
   - `backend/learning/adapters/local_feedback.py`
   - `backend/web/static/js/gustav.js`
   - `api/openapi.yml`
3. Gezielte Testausfuehrung der betroffenen Slices

## Tests
- `backend/tests/learning_adapters/test_local_feedback_dspy.py`
- `backend/tests/test_teaching_live_js_behaviour.py`
- `backend/tests/test_openapi_teaching_live_student_overview_contract.py`
