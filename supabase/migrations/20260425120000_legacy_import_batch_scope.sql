-- Make legacy import runs batch-scoped for production-safe testing.
--
-- Why:
--   Legacy import tests must be able to run against a shared real database
--   without processing or cleaning unrelated staging rows.  The migration
--   keeps existing manual imports compatible: staging tables are still created
--   by import runbooks, but when they exist they can carry import_batch_id.

create table if not exists public.import_audit_runs (
  id uuid primary key default gen_random_uuid(),
  source text not null,
  started_at_utc timestamptz not null default now(),
  ended_at_utc timestamptz null,
  notes text null
);

alter table public.import_audit_runs
  add column if not exists batch_id uuid null;

create table if not exists public.import_audit_mappings (
  run_id uuid not null references public.import_audit_runs(id) on delete cascade,
  entity text not null,
  legacy_id text not null,
  target_table text not null,
  target_id text null,
  status text not null check (status in ('ok','skip','conflict','error')),
  reason text null,
  created_at_utc timestamptz not null default now()
);

create table if not exists public.legacy_user_map (
  legacy_id uuid primary key,
  sub text unique
);

do $$
declare
  staging_table text;
begin
  create schema if not exists staging;

  foreach staging_table in array array[
    'users',
    'courses',
    'course_students',
    'learning_units',
    'unit_sections',
    'course_unit_assignments',
    'section_releases',
    'materials_json',
    'tasks_base',
    'tasks_regular',
    'submissions'
  ]
  loop
    if to_regclass(format('staging.%I', staging_table)) is not null then
      execute format('alter table staging.%I add column if not exists import_batch_id uuid null', staging_table);
    end if;
  end loop;
end $$;
