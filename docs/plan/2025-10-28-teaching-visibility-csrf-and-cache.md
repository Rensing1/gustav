# 2025-10-28 — Teaching: Visibility CSRF + Cache Hardening

## User Story
Als Kursleiter möchte ich, dass das Freigeben/Verstecken von Abschnitten nur von derselben Origin aus erfolgen kann, damit fremde Webseiten (CSRF) keine Änderungen auslösen und Antworten nicht in (Zwischen‑)Caches landen.

## BDD Szenarien
- Given eine fremde Origin; When PATCH Visibility; Then 403 forbidden und `detail=csrf_violation`.
- Given dieselbe Origin; When PATCH Visibility `{ visible: true }`; Then 200 mit aktuellem Sichtbarkeits‑Record und `Cache-Control: private, no-store`.
- Given invalid UUIDs; When PATCH Visibility; Then 400 `bad_request` mit privatem Cache Header.

## API Contract (OpenAPI Ausschnitt)
- Pfad: `/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility` (PATCH)
  - Beschreibung ergänzt: CSRF‑Hinweis (Same‑Origin, Origin/Referer) → 403 `csrf_violation`.
  - Responses 200/400/401/403/404 enthalten Header `Cache-Control: private, no-store`.

## Migrationen (Supabase/PostgreSQL)
- Keine Schemaänderungen erforderlich.

## Tests (pytest)
- `backend/tests/test_teaching_visibility_csrf.py`
  - cross‑origin → 403 + `detail=csrf_violation` + privater Cache Header.
  - same‑origin → 200 + privater Cache Header.
  - invalid UUID → 400 + privater Cache Header.
- `backend/tests/test_openapi_teaching_visibility_contract.py`
  - OpenAPI enthält CSRF‑Hinweis und Cache‑Header (200/403) am PATCH‑Endpunkt.

## Minimaler Code (Red‑Green‑Refactor)
- Adapter: `backend/web/routes/teaching.py`
  - `_is_same_origin(request)` (Reuse aus Learning, proxy‑aware, Fallback Referer).
  - In Visibility‑Handler: CSRF‑Prüfung vor Validierung; Fehlerwege vereinheitlicht über `_private_error`.
  - Erfolgreiche 200 via `_json_private`.
- Doku: OpenAPI + `docs/references/teaching.md` + CHANGELOG (BREAKING‑Hinweis bereits vorhanden).

## Risiken
- Forwarded‑Header Spoofing: Nur wenn `GUSTAV_TRUST_PROXY=true` gesetzt. Sonst striktes Ablehnen.
- Client‑Aufwand: Browser müssen keine Tokens senden; Origin‑Header kommt automatisch bei CORS‑relevanten Requests.

