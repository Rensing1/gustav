# Production Run Checklist — Legacy → Alpha2

Use this concise checklist to run the migration in production once, end‑to‑end, with predictable results. For full commands see `docs/migration/final_run_playbook.md`.

## 1) Environment & Access
- Supabase stack up: `supabase status` reports running; psql connects to DB.
- Export DSN: `export SERVICE_ROLE_DSN='postgresql://postgres:postgres@<host>:5432/postgres'`.
- Export Storage env (if uploading materials): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.
- Keycloak reachable: `http://id.<domain>` with admin creds (realm `gustav`).

## 2) Backups & Rollback Plan
- Create DB snapshot (pg_dump/managed snapshot) before import.
- Archive storage buckets (materials, submissions) if replacing objects.
- Note: Submissions import is additive (increments `attempt_nr` on re-runs). Rollback is via DB restore.

## 3) Data Slices Ready
- `/tmp/legacy_stage/` contains:
  - `users_mapped.csv`, `courses.csv`, `course_students.csv`, `learning_units.csv`, `unit_sections.csv`,
    `course_unit_assignments.csv`, `section_releases.csv`, `tasks_base.csv`,
    `tasks_regular_final.csv`, `submissions_final.csv`.
- Materials metadata prepared (optional but recommended): `staging.materials_json` rows or generation script used.
- Storage blobs unpacked under `/tmp/legacy_storage/stub/stub` (only referenced keys will be uploaded).

## 4) Pre‑Flight (Staging Load)
- Create `staging.*` tables and truncate (idempotent).
- Load all CSVs into `staging.*` (see playbook; verify counts with quick `select count(*)` per table).
- Upload only referenced materials to Storage (URL‑encode object paths).

## 5) Identity Mapping (Keycloak)
- Run Keycloak-based mapping so RLS works for real users:
  - `.venv/bin/python -m backend.tools.sub_mapping_sync --from-keycloak ...`
- Optional: rewrite `staging.submissions.student_sub` to real SUBs using `legacy_user_map` to reduce `missing_course`.

## 6) Live Import (Run Once)
- Execute the CLI (creates audit tables automatically if missing):
  - `.venv/bin/python -m backend.tools.legacy_migration --db-dsn "$SERVICE_ROLE_DSN" --source "legacy-alpha1-prod-$(date +%F)" --batch-size 1000`
- Important: run only once to avoid extra submission attempts.

## 7) Post‑Run Verification
- Counts (public.*): courses, memberships, units, sections, modules, releases, materials, tasks, submissions (and distinct key for submissions).
- Audit: per‑entity/status summary from `public.import_audit_mappings` (store results with the run ID).
- RLS checks via `gustav_limited` role and `set local app.current_sub` for a known teacher and student.
- UI sanity: login as one teacher and one student; verify visible courses/units.

## 8) Remediation (Only if `missing_course` remains)
- Build suggestions (Top‑1 course per submission) and export CSVs:
  - `psql "$SERVICE_ROLE_DSN" -f docs/migration/sql/build_best_course_suggestions.sql`
- Apply modules/releases idempotently:
  - `psql "$SERVICE_ROLE_DSN" -v modules_csv=/tmp/modules_auto.csv -v releases_csv=/tmp/releases_auto.csv -f docs/migration/sql/apply_modules_and_releases.sql`
- Re‑run submissions phase via resume:
  - `RUN_ID=$(psql "$SERVICE_ROLE_DSN" -Atc "select id from public.import_audit_runs order by started_at_utc desc limit 1")`
  - `.venv/bin/python -m backend.tools.legacy_migration --db-dsn "$SERVICE_ROLE_DSN" --source re-run-$(date +%F) --resume-run "$RUN_ID"`

## 9) Close‑Out
- Record the final `RUN_ID`, store audit TSV/CSV outputs with the change ticket.
- Capture final table counts and RLS smoke results.
- Remove temporary files under `/tmp` if required by ops policy.

