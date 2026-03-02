# Plan: Teaching Live Matrix - H5P Score x/y je Schueler (letzter Versuch)

Status: geplant  
Datum: 2026-03-02

## Ziel / Motivation
In der Live-Unterrichts-Matrix ("Unterricht > Live") sollen Lehrkraefte bei H5P-Aufgaben pro Schueler direkt sehen, wie viele Punkte erreicht wurden.

Aktueller Zustand:
- Non-H5P Aufgaben: Matrix zeigt bei vorhandener Auswertung eine Badge mit `average_score` (0..10).
- H5P Aufgaben: Matrix zeigt aktuell Statussymbole (--- / • / ✓), aber keinen Punktestand.

Gewuenschter Zustand:
- H5P Aufgaben zeigen in der Matrix `score_raw/score_max` (z.B. `7/10`) statt der Statussymbole.

## Scope (MVP)
- Fuer `Task.kind="h5p"` wird in jeder Matrixzelle der H5P-Score als `x/y` angezeigt.
- Angezeigt wird der Score des letzten Versuchs ("latest submission") des Schuelers fuer diese Aufgabe im Kurs.
- Delta-Polling aktualisiert die betroffenen Zellen ohne Reload (HTMX OOB Updates).

## Nicht-Ziele
- Keine Abgaben-/Versuchshistorie in der UI.
- Keine Bestleistung-Anzeige (kein "best score").
- Keine per-Frage-Auswertung / kein xAPI Learning Record Store.

## Semantik (fixiert)
- Wenn keine Submission existiert: Anzeige `---`.
- Wenn eine Submission existiert: Anzeige `score_raw/score_max` des letzten Versuchs.
- Unscored H5P Inhalte koennen `0/0` melden; das wird als `0/0` angezeigt (und ist nicht mit "keine Submission" zu verwechseln).

## Contract-First: OpenAPI-Aenderungen
Datei: `api/openapi.yml`

1. `TeachingUnitTaskCell` (Summary Payload) erweitert um optionale Felder:
- `score_raw` (integer, nullable): Raw Score des letzten H5P-Versuchs (nur sinnvoll fuer H5P).
- `score_max` (integer, nullable): Max Score des letzten H5P-Versuchs (nur sinnvoll fuer H5P).

2. `TeachingUnitDeltaCell` (Delta Payload) erweitert um optionale Felder:
- `score_raw` (integer, nullable)
- `score_max` (integer, nullable)

Hinweis:
- Diese Felder sind additive Aenderungen (keine Breaking Changes).
- `h5p_completed` bleibt Bestandteil des Contracts (auch wenn die Matrix im MVP `x/y` rendert).

## DB / Migration (Supabase)
Problem:
- Lehrkraefte duerfen `public.learning_submissions` nicht direkt bulk lesen (RLS ist student-scoped).
- Die Live-Matrix nutzt daher einen SECURITY DEFINER Helper: `public.get_unit_latest_submissions_for_owner(...)`.

Loesung:
- Neue Migration unter `supabase/migrations/` (Timestamp nach Repo-Konvention).
- `public.get_unit_latest_submissions_for_owner(...)` wird um Rueckgabe-Felder `score_raw` und `score_max` erweitert (Score der latest Submission pro `(student_sub, task_id)`).

Technische Details:
- Da sich die RETURNS TABLE Signatur aendert, ist Drop+Create notwendig (Postgres: CREATE OR REPLACE kann OUT-Params nicht aendern).
- Security Hardening muss erhalten bleiben:
  - `security definer`
  - `set search_path = pg_catalog, public`
  - Owner-Bindung via `current_setting('app.current_sub', true)`
  - `revoke all ... from public` und `grant execute ... to gustav_limited`

## Backend (Teaching API)
Datei: `backend/web/routes/teaching.py`

1. Summary Endpoint:
- Route: `GET /api/teaching/courses/{course_id}/units/{unit_id}/submissions/summary`
- Helper-Select auf `get_unit_latest_submissions_for_owner` um `score_raw/score_max` erweitern.
- Fuer Zellen mit `Task.kind="h5p"` und `has_submission=true` werden `score_raw/score_max` in die Cell aufgenommen.

2. Delta Endpoint:
- Route: `GET /api/teaching/courses/{course_id}/units/{unit_id}/submissions/delta`
- Helper-Select ebenfalls um `score_raw/score_max` erweitern.
- Delta-Cells enthalten `score_raw/score_max`, damit SSR-Delta Fragmente denselben `x/y` Stand ohne Reload rendern koennen.

## UI (SSR Live Matrix)
Datei: `backend/web/main.py`

- `_render_live_cell_content(...)` so aendern, dass fuer H5P-Zellen bei vorhandener Submission `x/y` gerendert wird (statt •/✓).
- Empfehlung: Darstellung als Badge (Konsistenz zu existierenden Badges):
  - `<span class="badge" aria-label="Punkte 7 von 10">7/10</span>`
- Delta-Fragment Rendering (`/teaching/.../live/matrix/delta`) muss `score_raw/score_max` an die Rendering-Funktion durchreichen.

## Tests
1. OpenAPI Contract Tests:
- Datei: `backend/tests/test_openapi_teaching_live_unit_contract.py`
- Neue Assertions: `TeachingUnitTaskCell` und `TeachingUnitDeltaCell` haben Properties `score_raw` und `score_max`.

2. API Tests:
- Datei: `backend/tests/test_teaching_live_unit_summary_api.py`
  - H5P Summary enthaelt `score_raw/score_max` fuer H5P-Zellen (latest semantics).
- Datei: `backend/tests/test_teaching_live_unit_delta_api.py`
  - H5P Delta enthaelt `score_raw/score_max` fuer H5P-Zellen (latest semantics).

3. SSR UI Tests:
- Datei: `backend/tests/test_teaching_live_unit_ui_ssr.py`
  - Der bisherige Test, der `---/•/✓` fuer H5P erwartet, wird auf `x/y` umgestellt.
  - Delta-Fragment muss ebenfalls `x/y` enthalten.

## Akzeptanzkriterien
- In der Live-Matrix zeigt jede H5P-Zelle `---` oder `x/y` (letzter Versuch).
- Nach einem neuen H5P-Versuch aktualisiert das Delta-Polling die Anzeige auf das neue `x/y`.
- Non-H5P Matrixverhalten bleibt unveraendert.
- Privacy/Security Header bleiben: `Cache-Control: private, no-store`, `Vary: Origin`.

## Rollout / Reihenfolge
Empfohlene Reihenfolge fuer eine spaetere Implementierung:
1. DB Migration (Helper erweitert)
2. Backend (Summary/Delta liefern neue Felder)
3. UI Rendering (zeigt `x/y`)
4. Tests gruen
