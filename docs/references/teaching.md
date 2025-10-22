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
  - 204, entfernt auch Mitgliedschaften; 404 wenn Kurs nicht existiert; 403 wenn nicht Owner
- `GET /api/teaching/courses/{course_id}/members?limit&offset` (Owner only)
  - 200 `[CourseMember { sub, name, joined_at }]`; 404 wenn Kurs nicht existiert; 403 wenn nicht Owner
- `POST /api/teaching/courses/{course_id}/members` (Owner only, idempotent)
  - Body `{ student_sub }`
  - 201 neu, 204 existierend, 400/403/404
- `DELETE /api/teaching/courses/{course_id}/members/{student_sub}` (Owner only, idempotent)
  - 204; 404 wenn Kurs nicht existiert; 403 wenn nicht Owner
- `GET /api/users/search?q=&role=student&limit` (Users‑Namespace)
  - Nur Teacher/Admin. Mindestlänge `q ≥ 2`, Limit-Cap `≤ 50`
  - 200 `[{ sub, name }]`, 400/403

### Lerneinheiten & Kursmodule
- `GET /api/teaching/units?limit&offset` (Teacher only)
  - 200 `[{ id, title, summary?, author_id, created_at, updated_at }]`
- `POST /api/teaching/units` (Teacher only)
  - Body `{ title, summary? }`, 201 `Unit` oder 400/403
- `PATCH /api/teaching/units/{unit_id}` (Author only)
  - 200 `Unit` oder 400/403/404
- `DELETE /api/teaching/units/{unit_id}` (Author only)
  - 204 oder 403/404
- `GET /api/teaching/courses/{course_id}/modules` (Owner only)
  - 200 `[{ id, course_id, unit_id, position, context_notes?, created_at, updated_at }]`
- `POST /api/teaching/courses/{course_id}/modules` (Owner only)
  - Body `{ unit_id, context_notes? }`, 201 `CourseModule`; 403 wenn nicht Owner/Autor; 404 wenn Kurs/Unit fehlt; 409 bei Duplicate
- `POST /api/teaching/courses/{course_id}/modules/reorder` (Owner only)
  - Body `{ module_ids: [uuid,…] }` repräsentiert die Zielreihenfolge; 200 mit neuer Reihenfolge; 400 bei Duplikaten/Inkonsistenzen; 404/403 wie oben
- `PATCH /api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility` (Owner only)
  - Body `{ visible: bool }`, 200 `ModuleSectionVisibility`
  - 400 mit `detail`: `invalid_course_id | invalid_module_id | invalid_section_id | missing_visible | invalid_visible_type`
  - 403 wenn nicht Owner; 404 wenn Abschnitt nicht zum Modul gehört

#### Abschnitte (Sections) je Lerneinheit
- `GET /api/teaching/units/{unit_id}/sections` (Author only)
  - 200 `[{ id, unit_id, title, position, created_at, updated_at }]`; 403/404 gemäß Ownership‑Guard; 400 bei ungültiger UUID
- `POST /api/teaching/units/{unit_id}/sections` (Author only)
  - Body `{ title[1..200] }`, 201 `Section` am Ende (nächste `position`); 400/403/404
- `PATCH /api/teaching/units/{unit_id}/sections/{section_id}` (Author only)
  - Body `{ title[1..200] }` (optional, aber nicht leer), 200 `Section`; 400/404/403
- `DELETE /api/teaching/units/{unit_id}/sections/{section_id}` (Author only)
  - 204; verbleibende Abschnitte werden auf `position = 1..n` resequenziert; 400/404/403
- `POST /api/teaching/units/{unit_id}/sections/reorder` (Author only)
  - Body `{ section_ids: [uuid,…] }` muss exakt die aktuelle ID‑Menge enthalten
  - 200 mit neuer Reihenfolge; 400 bei Duplikaten/Inkonsistenzen/Invalid‑UUID; 404 bei fachfremden IDs; 403 bei Ownership

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
- RLS: aktiviert, Zugriff mit Limited‑Role‑DSN im Backend (keine Service‑Role zur Laufzeit). Keine Grants an `anon`/`authenticated`.

Einheiten & Module: `supabase/migrations/20251021104017_teaching_units_modules.sql`
- `public.learning_units` (author‑scoped)
  - `id uuid pk`, `title text not null`, `summary text null`, `author_id text not null`
  - `created_at/updated_at` + Trigger, Index `idx_learning_units_author(author_id)`
- `public.course_modules` (per‑course order)
  - `id uuid pk`, `course_id uuid fk`, `unit_id uuid fk`, `position int > 0`, `context_notes text`
  - Uniques: `(course_id, position)` und `(course_id, unit_id)`; Trigger + Indizes
- RLS: Policies für Select/Insert/Update/Delete (Owner/Author‑gebunden); `SET LOCAL app.current_sub` steuert Identität
- Deferrable Constraint für Reorder: `supabase/migrations/20251021105921_teaching_course_modules_deferrable.sql`

Abschnitte (Sections): `supabase/migrations/20251021121841_teaching_unit_sections.sql`
- `public.unit_sections` (author‑scoped über Join auf `learning_units`)
  - `id uuid pk`, `unit_id uuid fk`, `title text not null`, `position int > 0`
  - `created_at/updated_at` + Trigger; Index `idx_unit_sections_unit(unit_id)`
- RLS: Select/Insert/Update/Delete nur, wenn `learning_units.author_id = app.current_sub`
- Ordering: Unique `(unit_id, position) DEFERRABLE INITIALLY IMMEDIATE` für atomare Reorders
- Reorder‑Semantik: Mengen‑Gleichheit, keine Duplikate, nur UUIDs; Cross‑Unit‑IDs → 404

Abschnittsfreigaben: `supabase/migrations/20251022135746_teaching_module_section_releases.sql`
- `public.module_section_releases`
  - `course_module_id uuid fk` → `course_modules(id)` on delete cascade
  - `section_id uuid fk` → `unit_sections(id)` on delete cascade
  - `visible boolean not null`
  - `released_at timestamptz null` (Zeitpunkt der letzten Freigabe)
  - `released_by text null` (OIDC `sub` der Lehrkraft)
  - PK `(course_module_id, section_id)`, Indizes auf `course_module_id`, `section_id`
- RLS: Owner-only via Join `course_modules` ↔ `courses` (`teacher_id = app.current_sub`)
- Insert/Update erzwingen Zugehörigkeit des Abschnitts zur Unit des Moduls sowie `released_by = caller`

RLS Policies & DSN
- Migration: `supabase/migrations/20251020154107_teaching_rls_policies.sql`
- Folgeanpassungen:
  - `supabase/migrations/20251020155746_teaching_rls_fix_and_sessions.sql` (Rekursion fix, Sessions‑RLS)
  - `supabase/migrations/20251020174347_memberships_select_self_only_and_fn.sql` (SELECT Self‑Only + Helper‑Funktion)
  - `supabase/migrations/20251020174657_memberships_insert_any_policy_restore.sql` (INSERT‑Policy für App‑Rolle)
  - `supabase/migrations/20251020181043_memberships_select_any_restore.sql` (Zwischenstand – volle Leserechte; durch nächste Migration gehärtet)
  - `supabase/migrations/20251020182801_memberships_owner_or_self_restore.sql` (Re-harden self-only SELECT + Helper reapply)
  - `supabase/migrations/20251020183625_memberships_self_only_fix.sql` (Final self-only SELECT + helper bounds refresh; INSERT bleibt App-gesteuert)
  - `supabase/migrations/20251020184810_app_sessions_rls_restrict.sql` (Entzieht `gustav_limited` den Zugriff auf Sessions)
- App-Runtime: Eine DSN mit Limited‑Role (z. B. `gustav_limited`). RLS greift immer.
- Backend setzt je Query `SET LOCAL app.current_sub = '<sub>'`, damit Policies wissen, „wer“ handelt.
- Owner‑Mitgliederliste erfolgt über `public.get_course_members(owner_sub, course_id, limit, offset)` (SECURITY DEFINER), um RLS‑Rekursionen zu vermeiden.
- Migrationen laufen getrennt über das Supabase‑CLI (Owner/Service), die App muss nie umschalten.
 - Existence/Ownership‑Helper (SECURITY DEFINER): `supabase/migrations/20251021081254_teaching_course_existence_helpers.sql`
   - `public.course_exists_for_owner(owner_sub text, course_id uuid) returns boolean`
   - `public.course_exists(course_id uuid) returns boolean`

Tests
- API‑Tests erzeugen Daten über die API (RLS‑konform).
- Optionaler RLS‑Test nutzt nur eine DSN (Limited) und seedet per `set_config('app.current_sub', ...)`.

Anwenden lokal:
- `supabase migration up`
- Rückgängig: `supabase migration down 1`

DSN (Beispiel): `DATABASE_URL=postgresql://gustav_limited:gustav-limited@127.0.0.1:54322/postgres`

## Sicherheit & Datenschutz
- Owner‑Policy: Nur Kurs‑Autor (teacher_id == sub) verwaltet Kurs/Mitglieder und sieht Mitgliederliste.
- Kein PII in DTOs: Identität über `sub`; `name` wird für Mitglieder über Directory-Adapter aufgelöst.
- Pagination mit Limit‑Cap (DoS‑Schutz). Suche: Mindestlänge `q`.
- Responses der Auth‑abhängigen Endpunkte sind nicht cachebar (Middleware regelt 401 JSON).
 - Semantik: Nicht‑existenter Kurs → 404 (Not Found); Nicht‑Owner → 403 (Forbidden). Gilt konsistent für Members‑Endpunkte und Delete.
 - Sections/Units: Nicht‑existente Unit → 404; Nicht‑Author → 403 (über Guard mit Existenz‑Helpern). UUID‑Fehler → 400 (kein 422).

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
