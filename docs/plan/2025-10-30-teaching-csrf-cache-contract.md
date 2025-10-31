# Plan: Teaching-CSRF auf Schreibendpunkten + Cache-Contract

Datum: 2025-10-30
Autor: Felix / GUSTAV-Team

## User Story
Als Lehrkraft möchte ich, dass alle schreibenden Teaching-APIs (Kurs/Unit/Abschnitt/Material/Task/Members/Reorder) durch einen Same‑Origin‑CSRF‑Check geschützt sind, damit Cross‑Site‑Anfragen geblockt werden. Gleichzeitig sollen erfolgreiche 200/201‑Antworten private Cache‑Header tragen, damit keine personenbezogenen Daten in Browser/Proxies landen.

## BDD-Szenarien
- Given gültige Session (teacher), When POST /api/teaching/courses with Origin=http://evil.local, Then 403 with detail=csrf_violation and Cache-Control=private, no-store
- Given gültige Session (teacher), When POST /api/teaching/courses with Origin=http://test, Then 201 with Cache-Control=private, no-store
- Given gültige Session (teacher), When POST /api/teaching/units with Origin=http://evil.local, Then 403 csrf_violation
- Given gültige Session (teacher), When PATCH /api/teaching/units/{id} with Origin=http://test, Then 200 with Cache-Control=private, no-store
- Given gültige Session (teacher), When PATCH visibility cross-origin, Then 403 csrf_violation (Regression)

## API Contract (OpenAPI-Ausschnitte)
- POST /api/teaching/courses: +x-security-notes: CSRF Same-origin; 201 -> headers.Cache-Control: private, no-store
- POST /api/teaching/units: +x-security-notes: CSRF Same-origin; 201 -> headers.Cache-Control
- PATCH /api/teaching/units/{unit_id}: +x-security-notes: CSRF Same-origin; 200 -> headers.Cache-Control
- PATCH /api/teaching/courses/{course_id}: +x-security-notes: CSRF Same-origin; 200 -> headers.Cache-Control

## Migration (Supabase/PostgreSQL)
Ziel: EXECUTE-Rechte explizit der App-Rolle geben und PUBLIC entziehen, damit RLS‑Hilfsfunktionen nicht unbeabsichtigt offen sind.

```sql
set search_path = public, pg_temp;
revoke all on function public.student_is_course_member(text, uuid) from public;
grant execute on function public.student_is_course_member(text, uuid) to gustav_limited;
revoke all on function public.student_can_access_unit(text, uuid) from public;
grant execute on function public.student_can_access_unit(text, uuid) to gustav_limited;
revoke all on function public.student_can_access_course_module(text, uuid) from public;
grant execute on function public.student_can_access_course_module(text, uuid) to gustav_limited;
revoke all on function public.student_can_access_section(text, uuid) from public;
grant execute on function public.student_can_access_section(text, uuid) to gustav_limited;
```

## Tests (pytest)
- backend/tests/test_teaching_csrf_other_writes.py
  - Given teacher + cross-origin, When POST /api/teaching/courses, Then 403 csrf_violation + private,no-store
  - Given teacher + same-origin, When POST /api/teaching/courses, Then 201 + private,no-store
  - Given teacher + cross-origin, When POST /api/teaching/units, Then 403 csrf_violation + private,no-store
- Regression: backend/tests/test_teaching_visibility_csrf.py (unverändert grün)
- Regression: backend/tests/test_api_cache_headers_write_endpoints.py (private,no-store)

## Umsetzung
- Teaching-Router: dedizierte Helper `_csrf_guard(request)` hinzufügen und in allen Write‑Handlers anwenden (POST/PATCH/DELETE inkl. Reorder, Materials/Tasks, Members, Modules).
- OpenAPI: CSRF-Hinweise und Cache-Control-Header auf create/update ergänzen (weitere Endpunkte sukzessive angleichen).
- Migration: EXECUTE‑GRANTS für student_*‑RLS‑Hilfsfunktionen.

## Risiken/Abwägungen
- Origin/Referer-Validierung ist proxy-bewusst (GUSTAV_TRUST_PROXY). Non‑browser‑Clients ohne Header bleiben funktionsfähig.
- Cache-Policy private,no-store ist konservativ; Performanceauswirkungen minimal (Lehrer-UI ist personalisiert).

