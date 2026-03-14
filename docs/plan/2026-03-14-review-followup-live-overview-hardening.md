# Plan: Review Follow-up fuer Live Overview Hardening

Status: in Arbeit
Datum: 2026-03-14

## Ziel
Drei kleine Review-Feststellungen sollen ohne Umbau behoben werden:

- deterministische Feedback-Parsefehler robuster als `feedback_invalid_analysis` klassifizieren
- In-Memory-Fallback fuer kursweite Aufgabenlisten stabil nach Abschnitts- und Aufgabenreihenfolge sortieren
- SSR-Metadaten der Schueler-Live-Ansicht staerker am Teaching-API-Verhalten ausrichten

## Warum
- Der Feedback-Adapter soll bei stabilen Strukturfehlern nicht unnoetig retryn.
- Der In-Memory-Fallback wird in Tests und Offline-Szenarien genutzt und soll dasselbe Reihenfolgeverhalten wie die DB liefern.
- Die SSR-Ansicht soll dieselben Fehler- und Datenpfade wie die API verwenden, damit UI und Vertrag nicht auseinanderlaufen.

## Umsetzung
1. Regressionstests fuer:
   - `invalid_criterion_idx` mit Zusatztext
   - Aufgabenreihenfolge ueber mehrere Abschnitte im In-Memory-Repo
   - SSR-Live-Seite bei fehlenden Repo-Metadaten mit API-Fallback
2. Minimale Codeanpassungen in:
   - `backend/learning/adapters/local_feedback.py`
   - `backend/web/routes/teaching.py`
   - `backend/web/main.py`
3. Gezielte Testausfuehrung der betroffenen Slices

## Tests
- `backend/tests/learning_adapters/test_local_feedback_dspy.py`
- `backend/tests/test_teaching_live_student_overview_api.py`
- `backend/tests/test_teaching_live_student_overview_ssr.py`
- neue In-Memory-Regression fuer `routes.teaching._Repo`
