# Changelog

## Unreleased
- fix(api/teaching): PATCH materials treats provided empty title as `invalid_title` (was `empty_payload`).
- consistency(api/teaching): GET materials returns explicit JSONResponse (200) for uniform response shape.
- docs(openapi): Add `empty_payload` example to materials PATCH 400 section.
- consistency(api/teaching): Align error detail strings — use `invalid_module_ids` (plural) and map no-sections case to `section_mismatch` in DB repo.
- security(api/teaching): Move author/owner guards before payload validation in Unit/Section PATCH to avoid error‑oracle leakage (403/404 precede 400 empty_payload).
- fix(teaching): Implement sections CRUD/reorder in in‑memory repo to avoid 500s in dev/tests without Postgres; add smoke test.
- fix(api/teaching): Return explicit JSONResponse (200) from sections/modules reorder for consistent API shape.
- security(api/teaching): Check course ownership before deep payload validation in modules reorder to reduce error‑oracle leakage (403/404 precede 400 list errors).
- security(api/teaching): Mirror early authorship guard for sections reorder to reduce error‑oracle leakage.
- docs(openapi): Add 400 examples for modules reorder (empty_reorder, invalid_module_ids, no_modules) and sections reorder (section_mismatch).
  Also add sections: empty_section_ids, section_ids_must_be_array examples.
- fix(api/openapi): Correct DELETE /api/teaching/units/{unit_id} path placement (remove stray delete under sections/reorder); units PATCH uses authorOnly permissions.
- fix(api/teaching): Validate course_id UUID in POST /api/teaching/courses/{course_id}/modules/reorder (400 bad_request on invalid path param).
- fix(api/teaching): Allow PATCH /materials to update `alt_text`, returning `invalid_alt_text` on violations; keeps markdown/body guards intact.
- security(teaching): Sanitize storage-key path segments (author/unit/section/material) before presign/finalize to avoid path traversal on S3-compatible backends; in-memory repo gained full file-material workflow.
- docs(openapi/db): Document new error details (`invalid_filename`, `mime_not_allowed`, `invalid_alt_text`) and storage-key sanitizing; contract examples extended.
- tests(teaching): Extend file-material contract tests for invalid filenames, uppercase MIME normalization, size limit, expired intents, alt-text updates and in-memory fallback coverage.
- fix(db/sections): Serialize concurrent section creation by locking parent learning_unit; add one-shot retry on unique violation; regression tests added.
- fix(db/sections): Ensure unique-violation retry fetches the inserted row before the cursor closes; regression test guards against cursor-already-closed errors.
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
