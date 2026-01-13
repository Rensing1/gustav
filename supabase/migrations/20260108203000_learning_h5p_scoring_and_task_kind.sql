-- Learning: H5P scoring submissions + expose task kind/config to student helpers
--
-- Why:
--   Phase 3 adds `Task.kind="h5p"` to the Learning context. Students don't
--   upload text/files for H5P; instead we persist scored attempts reported by
--   the H5P runtime (xAPI → score raw/max).
--
-- Notes:
--   - Trusted-content model: libraries are teacher/admin managed.
--   - For H5P tasks, `max_attempts` is intentionally *not* enforced by the DB.
--     (H5P has its own attempt limits; GUSTAV tracks attempts for analytics.)
--
-- Local = Prod: this migration is the only source of truth for schema changes.

set search_path = public, pg_temp;

-- ---------------------------------------------------------------------------
-- 1) learning_submissions: allow kind=h5p and store score (raw/max)
-- ---------------------------------------------------------------------------

alter table if exists public.learning_submissions
  add column if not exists score_raw integer null,
  add column if not exists score_max integer null;

do $$
begin
  if exists (
    select 1
      from pg_constraint
     where conrelid = 'public.learning_submissions'::regclass
       and conname = 'learning_submissions_kind_check'
  ) then
    alter table public.learning_submissions
      drop constraint learning_submissions_kind_check;
  end if;
exception when others then
  raise notice 'Skipping drop of learning_submissions_kind_check: %', sqlerrm;
end $$;

alter table public.learning_submissions
  add constraint learning_submissions_kind_check
  check (kind in ('text','image','file','h5p'));

alter table if exists public.learning_submissions
  drop constraint if exists learning_submissions_score_check;

alter table public.learning_submissions
  add constraint learning_submissions_score_check
  check (
    (score_raw is null and score_max is null)
    or (
      score_raw is not null and score_max is not null
      and score_raw >= 0 and score_max >= 0 and score_raw <= score_max
    )
  );

alter table if exists public.learning_submissions
  drop constraint if exists learning_submissions_h5p_kind;

-- H5P submissions must not carry text/upload fields and must carry a score.
-- Non-H5P submissions must not carry score fields.
alter table public.learning_submissions
  add constraint learning_submissions_h5p_kind
  check (
    (kind = 'h5p' and
      score_raw is not null and score_max is not null and
      text_body is null and storage_key is null and mime_type is null and size_bytes is null and sha256 is null
    )
    or
    (kind <> 'h5p' and score_raw is null and score_max is null)
  );

-- ---------------------------------------------------------------------------
-- 2) Learning helper functions: include task kind + H5P config
-- ---------------------------------------------------------------------------

-- NOTE: Postgres cannot change a RETURNS TABLE (OUT params) signature via
-- CREATE OR REPLACE. We must drop first, then recreate with the new columns.
drop function if exists public.get_released_tasks_for_student(text, uuid, uuid);
create function public.get_released_tasks_for_student(
  p_student_sub text,
  p_course_id uuid,
  p_section_id uuid
)
returns table (
  id uuid,
  instruction_md text,
  criteria text[],
  hints_md text,
  due_at_iso text,
  max_attempts integer,
  kind text,
  h5p_content_id text,
  h5p_display_options jsonb,
  task_position integer,
  created_at_iso text,
  updated_at_iso text
)
language sql
security invoker
set search_path = public, pg_temp
as $$
  select
    t.id,
    t.instruction_md,
    t.criteria,
    t.hints_md,
    case
      when t.due_at is null then null
      else to_char(t.due_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
    end,
    t.max_attempts,
    t.kind,
    t.h5p_content_id,
    t.h5p_display_options,
    t.position as task_position,
    to_char(t.created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
    to_char(t.updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
  from public.course_memberships cm
  join public.course_modules mod on mod.course_id = cm.course_id
  join public.module_section_releases r
    on r.course_module_id = mod.id
   and r.section_id = p_section_id
   and coalesce(r.visible, false) = true
  join public.unit_sections s on s.id = p_section_id and s.unit_id = mod.unit_id
  join public.unit_tasks t on t.section_id = s.id
  where cm.course_id = p_course_id
    and cm.student_id = p_student_sub
  order by t.position, t.id;
$$;

drop function if exists public.get_task_metadata_for_student(text, uuid, uuid);
create function public.get_task_metadata_for_student(
  p_student_sub text,
  p_course_id uuid,
  p_task_id uuid
)
returns table (
  task_id uuid,
  section_id uuid,
  unit_id uuid,
  kind text,
  h5p_content_id text,
  max_attempts integer,
  criteria text[]
)
language sql
security invoker
set search_path = pg_catalog, public
as $$
  select
    t.id,
    t.section_id,
    t.unit_id,
    t.kind,
    t.h5p_content_id,
    t.max_attempts,
    t.criteria
  from public.course_memberships cm
  join public.course_modules m on m.course_id = cm.course_id
  join public.unit_sections s on s.unit_id = m.unit_id
  join public.unit_tasks t on t.section_id = s.id
  join public.module_section_releases r on r.course_module_id = m.id
                                  and r.section_id = s.id
  where cm.course_id = p_course_id
    and cm.student_id = p_student_sub
    and t.id = p_task_id
    and coalesce(r.visible, false) = true
  limit 1;
$$;

-- ---------------------------------------------------------------------------
-- 3) SECURITY: align privileges/ownership with other learning helpers
-- ---------------------------------------------------------------------------

-- Functions are invoked by the backend role only; do not leave them executable
-- by PUBLIC (Postgres default when creating a function).
revoke all on function public.get_released_tasks_for_student(text, uuid, uuid) from public;
grant execute on function public.get_released_tasks_for_student(text, uuid, uuid) to gustav_limited;

revoke all on function public.get_task_metadata_for_student(text, uuid, uuid) from public;
grant execute on function public.get_task_metadata_for_student(text, uuid, uuid) to gustav_limited;

-- Best-effort: keep ownership consistent (avoid BYPASSRLS owners).
do $$
begin
  if to_regprocedure('public.get_released_tasks_for_student(text, uuid, uuid)') is not null then
    begin
      alter function public.get_released_tasks_for_student(text, uuid, uuid) owner to gustav_limited;
    exception when insufficient_privilege then
      raise notice 'Skipping owner change for get_released_tasks_for_student: insufficient privileges';
    end;
  end if;

  if to_regprocedure('public.get_task_metadata_for_student(text, uuid, uuid)') is not null then
    begin
      alter function public.get_task_metadata_for_student(text, uuid, uuid) owner to gustav_limited;
    exception when insufficient_privilege then
      raise notice 'Skipping owner change for get_task_metadata_for_student: insufficient privileges';
    end;
  end if;
end $$;
