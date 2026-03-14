# Plan: Learning Feedback - deterministische Analysefehler terminal behandeln

Status: umgesetzt (2026-03-14)
Datum: 2026-03-14

## Ergebnis
- Neuer oeffentlicher Fehlercode `feedback_invalid_analysis` in
  `api/openapi.yml`.
- Neue Migration
  `supabase/migrations/20260314124500_learning_worker_feedback_invalid_analysis.sql`
  erweitert Constraint und Worker-Helper.
- Der lokale Feedback-Adapter mappt `invalid_criterion_idx` jetzt auf einen
  permanenten Fehler statt auf einen Retry-Pfad.
- Der Worker markiert betroffene Abgaben terminal als
  `feedback_invalid_analysis` und schreibt denselben Code auch auf den Job.
- Verifiziert mit:
  - `backend/tests/learning_adapters/test_local_feedback_dspy.py`
  - `backend/tests/test_learning_worker_jobs.py`
  - `backend/tests/test_learning_worker_security.py`
  - `backend/tests/test_learning_worker_error_codes.py`

## Ziel
Wenn die strukturierte DSPy-Analyse eine ungueltige `criterion_idx`-Liste
liefert, soll der Worker den Fall ohne Retry terminal als
`feedback_invalid_analysis` markieren.

## Produktentscheidungen
- Kein Retry fuer deterministische Parse-/Schemafehler
- Kein Fallback auf alternative Analyse oder heuristische Reparatur
- Praeziser oeffentlicher Fehlercode statt pauschalem `feedback_failed`

## Contract-First
- `api/openapi.yml` erweitert den Submission-`error_code` um
  `feedback_invalid_analysis`

## Datenbank / Migration
- Neue Migration erweitert:
  - `learning_submissions_error_code_check`
  - `public.learning_worker_update_failed(...)`

## Red-Green-Refactor
1. RED:
   - Adapter-/Worker-Tests fuer duplicate, missing und out-of-range
     `criterion_idx`
   - Security-/DB-Tests fuer neuen Error-Code
2. GREEN:
   - Feedback-Adapter mappt `invalid_criterion_idx` auf einen permanenten
     Fehler
   - Worker speichert `feedback_invalid_analysis` ohne Retry
3. REFACTOR:
   - Fehlerklassifikation klein und lesbar kapseln

## Verifikation
- `backend/tests/learning_adapters/test_dspy_overall_score_derived.py`
- `backend/tests/test_learning_worker_jobs.py`
- `backend/tests/test_learning_worker_security.py`
