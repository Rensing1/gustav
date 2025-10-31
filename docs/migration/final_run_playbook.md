# Final Migration Playbook (Production-Ready)

Purpose: Perform the legacy → Alpha2 import once, end‑to‑end, without manual fixes. This playbook folds in the lessons from the final test run.

## Prerequisites
- Supabase available (`supabase status`) and service DSN exported:
  - `export SERVICE_ROLE_DSN='postgresql://postgres:postgres@127.0.0.1:54322/postgres'`
- Keycloak reachable (via reverse proxy): `http://id.localhost:8100` (admin creds).
- Legacy CSV slices exist under `/tmp/legacy_stage/` (see `legacy_export_cookbook.md`).
- Storage blobs unpacked under `/tmp/legacy_storage/stub/stub`.

## 1) Staging schema and CSV load (idempotent)
```
psql "$SERVICE_ROLE_DSN" <<'SQL'
create schema if not exists staging;
create table if not exists staging.users(id uuid primary key, sub text not null);
create table if not exists staging.courses(id uuid primary key, title text not null, creator_id uuid not null);
create table if not exists staging.course_students(course_id uuid, student_id uuid, created_at timestamptz);
create table if not exists staging.learning_units(id uuid primary key, title text not null, description text, creator_id uuid not null);
create table if not exists staging.unit_sections(id uuid primary key, unit_id uuid not null, title text not null, order_in_unit int);
create table if not exists staging.course_unit_assignments(course_id uuid, unit_id uuid, position int);
create table if not exists staging.section_releases(course_id uuid, unit_id uuid, section_id uuid, visible boolean, released_at timestamptz);
create table if not exists staging.materials_json (id uuid, section_id uuid, kind text, title text, body_md text, storage_key text, mime_type text, size_bytes bigint, sha256 text, position int, created_at timestamptz, legacy_url text);
create table if not exists staging.tasks_base(id uuid, instruction_md text, assessment_criteria jsonb, hints_md text);
create table if not exists staging.tasks_regular(id uuid, section_id uuid, order_in_section int, max_attempts int, created_at timestamptz);
create table if not exists staging.submissions(id uuid primary key, task_id uuid not null, student_sub text not null, kind text not null, text_body text, storage_key text, mime_type text, size_bytes bigint, sha256 text, created_at timestamptz);
truncate table staging.users, staging.courses, staging.course_students, staging.learning_units, staging.unit_sections, staging.course_unit_assignments, staging.section_releases, staging.materials_json, staging.tasks_base, staging.tasks_regular, staging.submissions;
SQL

psql "$SERVICE_ROLE_DSN" -c "\\copy staging.users from '/tmp/legacy_stage/users_mapped.csv' with (format csv, header true)"
psql "$SERVICE_ROLE_DSN" -c "\\copy staging.courses from '/tmp/legacy_stage/courses.csv' with (format csv, header true)"
psql "$SERVICE_ROLE_DSN" -c "\\copy staging.course_students from '/tmp/legacy_stage/course_students.csv' with (format csv, header true)"
psql "$SERVICE_ROLE_DSN" -c "\\copy staging.learning_units from '/tmp/legacy_stage/learning_units.csv' with (format csv, header true)"
psql "$SERVICE_ROLE_DSN" -c "\\copy staging.unit_sections from '/tmp/legacy_stage/unit_sections.csv' with (format csv, header true)"
psql "$SERVICE_ROLE_DSN" -c "\\copy staging.course_unit_assignments from '/tmp/legacy_stage/course_unit_assignments.csv' with (format csv, header true)"
psql "$SERVICE_ROLE_DSN" -c "\\copy staging.section_releases from '/tmp/legacy_stage/section_releases.csv' with (format csv, header true)"
psql "$SERVICE_ROLE_DSN" -c "\\copy staging.tasks_base from '/tmp/legacy_stage/tasks_base.csv' with (format csv, header true)"
psql "$SERVICE_ROLE_DSN" -c "\\copy staging.tasks_regular from '/tmp/legacy_stage/tasks_regular_final.csv' with (format csv, header true)"
psql "$SERVICE_ROLE_DSN" -c "\\copy staging.submissions from '/tmp/legacy_stage/submissions_final.csv' with (format csv, header true)"
```

## 2) Storage materials → staging + upload
Ensure `staging.materials_json` contains rows with `kind='file'` and valid metadata. Then upload only referenced keys:
```
psql "$SERVICE_ROLE_DSN" -F $'\t' -Atc "select storage_key, mime_type from staging.materials_json where kind='file' and storage_key is not null and mime_type is not null" > /tmp/material_keys.tsv
while IFS=$'\t' read -r storage_key mime; do
  rel_path=${storage_key#section_materials/}
  file_path="/tmp/legacy_storage/stub/stub/section_materials/$rel_path"
  [ -f "$file_path" ] || { echo "skip $file_path" >&2; continue; }
  enc_path=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$rel_path")
  curl -s -X POST "$SUPABASE_URL/storage/v1/object/section_materials/$enc_path" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Content-Type: $mime" -H "x-upsert: true" --data-binary @"$file_path" >/dev/null
done < /tmp/material_keys.tsv
```

## 3) Keycloak‑SUB‑Mapping (mandatory)
```
.venv/bin/python -m backend.tools.sub_mapping_sync \
  --db-dsn "$SERVICE_ROLE_DSN" \
  --from-keycloak \
  --legacy-dsn postgresql://postgres:postgres@127.0.0.1:54322/legacy_tmp \
  --kc-base-url http://127.0.0.1:8100 \
  --kc-host-header id.localhost \
  --realm gustav \
  --kc-admin-user admin \
  --kc-admin-pass admin

# Optional: staging.submissions auf echte SUBs mappen (verkürzt missing_course-Fälle)
psql "$SERVICE_ROLE_DSN" -c "update staging.submissions s set student_sub = m.sub from public.legacy_user_map m where s.student_sub = 'legacy:'||m.legacy_id::text"
```

## 4) Live‑Import (once)
```
.venv/bin/python -m backend.tools.legacy_migration \
  --db-dsn "$SERVICE_ROLE_DSN" \
  --source "legacy-alpha1-prod-$(date +%F)" \
  --batch-size 1000
```

Note: Run this only once on a clean target. Re-running will import additional
attempts for submissions (attempt_nr increases by design).

## 5) Optional Fallback (auto‑fix modules/releases for remaining missing_course)
When some submissions still skip with `missing_course`, build suggestions and apply:
```
psql "$SERVICE_ROLE_DSN" -f docs/migration/sql/build_best_course_suggestions.sql
psql "$SERVICE_ROLE_DSN" -v modules_csv=/tmp/modules_auto.csv -v releases_csv=/tmp/releases_auto.csv -f docs/migration/sql/apply_modules_and_releases.sql

# Re-run only submissions via resume
RUN_ID=$(psql "$SERVICE_ROLE_DSN" -Atc "select id from public.import_audit_runs order by started_at_utc desc limit 1")
.venv/bin/python -m backend.tools.legacy_migration --db-dsn "$SERVICE_ROLE_DSN" --source re-run-$(date +%F) --resume-run "$RUN_ID"
```

## Verification
- Counts: courses, memberships, units, sections, modules, releases, materials, tasks, submissions (unique keys).
- Audit summary by entity/status.
- RLS smoke test for a known teacher and student via `gustav_limited` role and `app.current_sub`.
