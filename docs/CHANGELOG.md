# Changelog

## Unreleased
- fix(api/openapi): Correct DELETE /api/teaching/units/{unit_id} path placement (remove stray delete under sections/reorder); units PATCH uses authorOnly permissions.
- fix(api/teaching): Validate course_id UUID in POST /api/teaching/courses/{course_id}/modules/reorder (400 bad_request on invalid path param).
- fix(db/sections): Serialize concurrent section creation by locking parent learning_unit; add one-shot retry on unique violation; regression tests added.
- security(teaching): Enforce limited-role DSN (gustav_limited) for TeachingRepo to guarantee RLS coverage; add override flag `ALLOW_SERVICE_DSN_FOR_TESTING` for dev only.
- fix(teaching): Correct HTTP semantics — 204 responses without body; align 404 vs 403 for members and delete endpoints with contract.
- feat(db): Add SECURITY DEFINER helpers `public.course_exists_for_owner` and `public.course_exists` via Supabase migration to disambiguate 404 (not found) from 403 (forbidden) safely.
- perf(teaching): Avoid blocking event loop during name resolution by offloading sync directory requests to a thread; foundation for future async/batch lookup.
- tests: Add DSN enforcement tests and optional existence-helper tests; strengthen assertions for 204 no-content responses.
- fix(api/teaching): PATCH /api/teaching/courses/{id} returns explicit JSONResponse (200) for consistent response shape.
- security(ops): /health responses include `Cache-Control: no-store` to prevent caching of diagnostics.
- test(auth): Add smoke test for `/auth/logout/success` (200 + back-to-login link).
- chore(auth): Remove deprecated `_cookie_opts` wrapper in auth routes; use shared `auth_utils.cookie_opts`.

## 2025-10-20
- Teaching (Unterrichten) — Kursmanagement (MVP)
  - OpenAPI erweitert: `Course`, `CourseCreate`, `CourseUpdate`, `CourseMember`
  - Endpunkte: Kurse (create/list/update/delete), Mitglieder (add/list/remove), Users‑Suche
  - Migration: `courses`, `course_memberships`, `pgcrypto`, `updated_at`‑Trigger, RLS
  - DB‑Repo (psycopg3) implementiert; Router standardmäßig DB bzw. Fallback In‑Memory in Tests
  - Tests: API‑Coverage und optionaler Repo‑Test (skip bei fehlender DB)
