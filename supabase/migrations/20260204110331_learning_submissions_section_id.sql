-- Learning: store `section_id` on submissions for modular unlock aggregation.
--
-- Why:
--   For modular units, students must not see the full task list of locked
--   modules. At the same time, the graph UI needs to compute `tasks_done` per
--   module without joining `unit_tasks` (content leak risk).
--
-- Strategy:
--   Denormalize the module's `section_id` onto each submission row so the
--   backend can aggregate progress without touching `unit_tasks`.
--
-- Notes:
--   This is a minimal MVP step. It does not attempt to keep `section_id`
--   in sync if a task is moved between sections.

set check_function_bodies = off;

-- ---------------------------------------------------------------------------
-- 1) Schema: learning_submissions.section_id + backfill + index
-- ---------------------------------------------------------------------------

alter table public.learning_submissions
  add column if not exists section_id uuid;

do $$
begin
  if not exists (
    select 1
      from pg_constraint c
      join pg_class t on t.oid = c.conrelid
      join pg_namespace n on n.oid = t.relnamespace
     where n.nspname = 'public'
       and t.relname = 'learning_submissions'
       and c.conname = 'learning_submissions_section_id_fkey'
  ) then
    alter table public.learning_submissions
      add constraint learning_submissions_section_id_fkey
        foreign key (section_id)
        references public.unit_sections(id)
        on delete cascade;
  end if;
end $$;

-- One-time backfill from the task metadata.
update public.learning_submissions ls
set section_id = t.section_id
from public.unit_tasks t
where t.id = ls.task_id
  and ls.section_id is null;

-- Fail fast if we cannot backfill cleanly (should never happen due to FK).
do $$
begin
  if exists (select 1 from public.learning_submissions where section_id is null) then
    raise exception 'learning_submissions.section_id backfill incomplete';
  end if;
end $$;

alter table public.learning_submissions
  alter column section_id set not null;

create index if not exists idx_learning_submissions_course_student_section
  on public.learning_submissions(course_id, student_sub, section_id);

-- ---------------------------------------------------------------------------
-- 2) Helpers: allow modular tasks in visibility checks (course-scoped)
-- ---------------------------------------------------------------------------

create or replace function public.check_task_visible_to_student(
  p_student_sub text,
  p_course_id uuid,
  p_task_id uuid
)
returns boolean
language sql
security invoker
set search_path = public, pg_temp
as $$
  select exists (
    select 1
      from public.course_memberships cm
      join public.unit_tasks t on t.id = p_task_id
      join public.course_modules m on m.unit_id = t.unit_id and m.course_id = p_course_id
     where cm.course_id = p_course_id
       and cm.student_id = p_student_sub
       and (
         -- Linear: section explicitly released by the teacher.
         exists (
           select 1
             from public.module_section_releases r
            where r.course_module_id = m.id
              and r.section_id = t.section_id
              and coalesce(r.visible, false) = true
         )
         or
         -- Modular: section is mapped as a module inside a modular unit.
         exists (
           select 1
             from public.unit_modules um
             join public.units u on u.id = um.unit_id
            where um.unit_id = t.unit_id
              and um.section_id = t.section_id
              and u.unit_type = 'modular'
         )
       )
  );
$$;

revoke all on function public.check_task_visible_to_student(text, uuid, uuid) from public;
grant execute on function public.check_task_visible_to_student(text, uuid, uuid) to gustav_limited;

create or replace function public.get_task_metadata_for_student(
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
  join public.unit_tasks t on t.unit_id = m.unit_id
  where cm.course_id = p_course_id
    and cm.student_id = p_student_sub
    and t.id = p_task_id
    and (
      -- Linear: section explicitly released by the teacher.
      exists (
        select 1
          from public.module_section_releases r
         where r.course_module_id = m.id
           and r.section_id = t.section_id
           and coalesce(r.visible, false) = true
      )
      or
      -- Modular: section is mapped as a module inside a modular unit.
      exists (
        select 1
          from public.unit_modules um
          join public.units u on u.id = um.unit_id
         where um.unit_id = t.unit_id
           and um.section_id = t.section_id
           and u.unit_type = 'modular'
      )
    )
  limit 1;
$$;

revoke all on function public.get_task_metadata_for_student(text, uuid, uuid) from public;
grant execute on function public.get_task_metadata_for_student(text, uuid, uuid) to gustav_limited;

set check_function_bodies = on;
