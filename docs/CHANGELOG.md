# Changelog

## 2025-10-20
- Teaching (Unterrichten) — Kursmanagement (MVP)
  - OpenAPI erweitert: `Course`, `CourseCreate`, `CourseUpdate`, `CourseMember`
  - Endpunkte: Kurse (create/list/update/delete), Mitglieder (add/list/remove), Users‑Suche
  - Migration: `courses`, `course_memberships`, `pgcrypto`, `updated_at`‑Trigger, RLS
  - DB‑Repo (psycopg3) implementiert; Router standardmäßig DB bzw. Fallback In‑Memory in Tests
  - Tests: API‑Coverage und optionaler Repo‑Test (skip bei fehlender DB)

