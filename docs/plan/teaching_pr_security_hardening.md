# Plan: Teaching PR Security Hardening

Ziel: Die Teaching-APIs (Kurse & Mitglieder) werden so gehärtet, dass
HTTP-Semantik vertragstreu ist (204 ohne Body; 404 vs. 403 sauber), RLS-
Sicherheitsannahmen unabhängig von der DSN-Konfiguration belastbar sind und
kritische Pfade durch Tests abgedeckt werden.

## Maßnahmen

1) API-Vertrag
- 204-Responses ohne Body gewährleisten; 404 für nicht existierende Kurse.
- Beschreibungen und Hinweise im OpenAPI-Contract schärfen.

2) DB-Migrationen
- SECURITY DEFINER-Helper:
  - `public.course_exists_for_owner(owner_sub, course_id) -> boolean`
  - `public.course_exists(course_id) -> boolean`
- Grant EXECUTE an `gustav_limited`.

3) Repo-Hardening (`backend/teaching/repo_db.py`)
- DSN-Check: Verlangt limited role (`gustav_limited`), sonst Fail-Closed, außer
  wenn `ALLOW_SERVICE_DSN_FOR_TESTING=true` gesetzt ist.
- Sicherheitsrelevante Updates/Deletes zusätzlich mit `teacher_id = $owner`.
- Hilfsmethoden `course_exists_for_owner`/`course_exists` für 404/403-Logik.

4) Routen-Hardening (`backend/web/routes/teaching.py`)
- 204-Responses ohne Body.
- Vor `GET/POST/DELETE` auf Kurs/Member: Ownership & Existenz prüfen und 404/403
  korrekt zurückgeben.

5) Tests
- 404 für unbekannten Kurs erzwingen (keine 403/404-Kombination).
- 204 ohne Body prüfen.
- Optionale DB-Tests für DSN-Policy (skip, wenn DB/Service-DSN nicht vorhanden).

## Rollout
- `supabase migration new` → Migration implementieren → `supabase migration up`.
- `pytest -q` lokal und in CI.

## Backout
- Migrationen sind idempotent (CREATE OR REPLACE), bei Bedarf Funktionen droppen.
- DSN-Check via `ALLOW_SERVICE_DSN_FOR_TESTING` übersteuerbar.

