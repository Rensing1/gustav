# Plan: Review Follow-up fuer SSR Fast-Path und DB-Preflight

Status: umgesetzt
Datum: 2026-03-14

## Ziel
Die Review-Feststellungen aus dem Vergleich `feature/teaching-live-student-overview` gegen `master`
werden mit kleinen, gezielten Aenderungen behoben:

- der SSR-Fast-Path fuer die Schueler-Live-Ansicht soll owner-scoped Repo-Helfer unter RLS korrekt nutzen
- der DB-Preflight soll neben `calliope` auch die neuen Maerz-Invarianten fuer Worker-Fehlercodes und H5P-Live-Helfer pruefen

## Warum
- Die SSR-Seite soll Course-Metadaten ohne unnoetigen internen HTTP-Fallback laden koennen.
- `make verify` soll frueh und praezise erkennen, wenn lokale Migrationen hinter dem erwarteten Schema-Stand liegen.

## Umsetzung
1. Regressionstests fuer:
   - owner-scoped Course-Lookup im SSR-Helfer
   - Preflight-Pruefung von `feedback_invalid_analysis`
   - Preflight-Pruefung der H5P-Live-Helfer-Spalten `score_raw/score_max`
2. Minimale Codeanpassungen in:
   - `backend/web/main.py`
   - `backend/tools/verify_db_preflight.py`
3. Gezielte Testausfuehrung der betroffenen Slices

## Tests
- `backend/tests/test_teaching_live_student_overview_ssr.py`
- `backend/tests/migration/test_verify_db_preflight.py`
