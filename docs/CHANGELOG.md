# Changelog

## Unreleased
- security(teaching): Enforce limited-role DSN (gustav_limited) for TeachingRepo to guarantee RLS coverage; add override flag `ALLOW_SERVICE_DSN_FOR_TESTING` for dev only.
- fix(teaching): Correct HTTP semantics — 204 responses without body; align 404 vs 403 for members and delete endpoints with contract.
- feat(db): Add SECURITY DEFINER helpers `public.course_exists_for_owner` and `public.course_exists` via Supabase migration to disambiguate 404 (not found) from 403 (forbidden) safely.
- perf(teaching): Avoid blocking event loop during name resolution by offloading sync directory requests to a thread; foundation for future async/batch lookup.
- tests: Add DSN enforcement tests and optional existence-helper tests; strengthen assertions for 204 no-content responses.

## 2025-10-20
- Teaching (Unterrichten) — Kursmanagement (MVP)
  - OpenAPI erweitert: `Course`, `CourseCreate`, `CourseUpdate`, `CourseMember`
  - Endpunkte: Kurse (create/list/update/delete), Mitglieder (add/list/remove), Users‑Suche
  - Migration: `courses`, `course_memberships`, `pgcrypto`, `updated_at`‑Trigger, RLS
  - DB‑Repo (psycopg3) implementiert; Router standardmäßig DB bzw. Fallback In‑Memory in Tests
  - Tests: API‑Coverage und optionaler Repo‑Test (skip bei fehlender DB)
