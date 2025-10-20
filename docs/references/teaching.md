# Unterrichten (Teaching) — Referenz

Ziel: Kursmanagement-API und -Schema dokumentieren. Lehrkräfte erstellen und verwalten Kurse, fügen Schüler hinzu/entfernen und sehen Mitglieder. Schüler sehen ihre belegten Kurse.

## Endpunkte (API)
- `GET /api/teaching/courses?limit&offset`
  - Lehrer: eigene Kurse; Schüler: belegte Kurse
  - 200 `[Course]`, 401/403 gemäß Auth-Middleware
- `POST /api/teaching/courses` (Teacher only)
  - Body `CourseCreate { title, subject?, grade_level?, term? }`
  - 201 `Course`, 400 bei ungültigen Feldern, 403 wenn nicht `teacher`
- `PATCH /api/teaching/courses/{course_id}` (Owner only)
  - Body `CourseUpdate` (alle Felder optional)
  - 200 `Course` oder 400/403/404
- `DELETE /api/teaching/courses/{course_id}` (Owner only)
  - 204, entfernt auch Mitgliedschaften
- `GET /api/teaching/courses/{course_id}/members?limit&offset` (Owner only)
  - 200 `[CourseMember { sub, name, joined_at }]`
- `POST /api/teaching/courses/{course_id}/members` (Owner only, idempotent)
  - Body `{ student_sub }`
  - 201 neu, 204 existierend, 400/403/404
- `DELETE /api/teaching/courses/{course_id}/members/{student_sub}` (Owner only, idempotent)
  - 204
- `GET /api/users/search?q=&role=student&limit` (Users‑Namespace)
  - Nur Teacher/Admin. Mindestlänge `q ≥ 2`, Limit-Cap `≤ 50`
  - 200 `[{ sub, name }]`, 400/403

Siehe OpenAPI: `api/openapi.yml` (Contract‑First, Quelle der Wahrheit).

## Schemas
- `Course { id, title, subject?, grade_level?, term?, teacher_id, created_at, updated_at }`
- `CourseCreate { title[1..200], subject?[≤100], grade_level?[≤32], term?[≤32] }`
- `CourseUpdate` (alle optional; gültige Längen wie oben, Validierung durch Server)
- `CourseMember { sub, name, joined_at }`

## Datenbank (PostgreSQL/Supabase)
Migration: `supabase/migrations/20251020150101_teaching_courses.sql`
- `public.courses`
  - `id uuid pk default gen_random_uuid()`
  - `title text not null`
  - `subject text null`, `grade_level text null`, `term text null`
  - `teacher_id text not null`
  - `created_at timestamptz default now()`, `updated_at timestamptz default now()`
  - Trigger `trg_courses_updated_at` (setzt `updated_at`)
  - Index `idx_courses_teacher(teacher_id)`
- `public.course_memberships`
  - `course_id uuid` fk → `courses(id)` on delete cascade
  - `student_id text not null`, `created_at timestamptz default now()`
  - PK `(course_id, student_id)`, Index `idx_course_memberships_student(student_id)`
- RLS: aktiviert, Zugriff über Service‑Role im Backend. Keine Grants an `anon`/`authenticated`.

RLS Policies & DSN
- Migrationen:
  - `supabase/migrations/20251020154107_teaching_rls_policies.sql` (Grundpolicies)
  - `supabase/migrations/20251020155746_teaching_rls_fix_and_sessions.sql` (Rekursion fix, Sessions‑RLS)
  - `supabase/migrations/20251020174347_memberships_select_self_only_and_fn.sql` (SELECT Self‑Only + Helper‑Funktion)
  - `supabase/migrations/20251020174657_memberships_insert_any_policy_restore.sql` (INSERT‑Policy für App‑Rolle)
- App-Runtime: Eine DSN mit Limited‑Role (z. B. `gustav_limited`). RLS greift immer.
- Backend setzt je Query `SET LOCAL app.current_sub = '<sub>'`, damit Policies wissen, „wer“ handelt.
- Owner‑Mitgliederliste erfolgt über `public.get_course_members(owner_sub, course_id, limit, offset)` (SECURITY DEFINER), um RLS‑Rekursionen zu vermeiden.
- Migrationen laufen getrennt über das Supabase‑CLI (Owner/Service), die App muss nie umschalten.

Tests
- API‑Tests erzeugen Daten über die API (RLS‑konform).
- Optionaler RLS‑Test nutzt nur eine DSN (Limited) und seedet per `set_config('app.current_sub', ...)`.

Anwenden lokal:
- `supabase migration up`
- Rückgängig: `supabase migration down 1`
- Alternativ mit psql: `psql "$DATABASE_URL" -f supabase/migrations/<timestamp>_*.sql`

DSN (Beispiel): `DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres`

## Sicherheit & Datenschutz
- Owner‑Policy: Nur Kurs‑Autor (teacher_id == sub) verwaltet Kurs/Mitglieder und sieht Mitgliederliste.
- Kein PII in DTOs: Identität über `sub`; `name` wird für Mitglieder über Directory-Adapter aufgelöst.
- Pagination mit Limit‑Cap (DoS‑Schutz). Suche: Mindestlänge `q`.
- Responses der Auth‑abhängigen Endpunkte sind nicht cachebar (Middleware regelt 401 JSON).

## Architektur & Adapter
- Web‑Adapter: `backend/web/routes/teaching.py`, `backend/web/routes/users.py`
- DB‑Repo: `backend/teaching/repo_db.py` (psycopg3)
- Directory‑Adapter: `search_users_by_name` / `resolve_student_names` sind mockbar und sollen in Zukunft Keycloak anbinden.

## Tests
- API: `backend/tests/test_teaching_courses_api.py`, `backend/tests/test_teaching_courses_update_delete_api.py`, `backend/tests/test_users_search_api.py`
- Repo (optional, benötigt DB): `backend/tests/test_teaching_repo_db_optional.py`

## DSGVO / Audit
- Timestamps `created_at`/`updated_at` an Kursen; `created_at` als `joined_at` bei Mitgliedschaften.
- Keine Mailadressen oder weiteren personenbezogenen Daten in API‑DTOs.
- Mitgliederliste auf Owner beschränkt.
