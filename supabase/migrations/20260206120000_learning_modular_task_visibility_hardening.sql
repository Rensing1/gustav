-- Learning: harden modular task visibility helpers (defense in depth).
--
-- Why:
--   `check_task_visible_to_student(...)` is used by RLS insert checks on
--   `learning_submissions`. For modular units we must only allow tasks from
--   modules that are currently open/done for the student in the course.
--
-- Scope:
--   - Add one shared helper for modular unlock evaluation.
--   - Rebuild check_task_visible_to_student / get_task_metadata_for_student
--     to use the same linear/modular visibility semantics.

set check_function_bodies = off;

create or replace function public.modular_section_is_open_or_done_for_student(
  p_student_sub text,
  p_course_id uuid,
  p_unit_id uuid,
  p_section_id uuid
)
returns boolean
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
  v_target_module_id uuid;
  v_section_tasks_done jsonb := '{}'::jsonb;
  v_done_by_module jsonb := '{}'::jsonb;
  v_incoming_ids uuid[];
  v_incoming_id uuid;
  v_prereq_required integer;
  v_prereq_done integer;
  v_tasks_total integer;
  v_raw_tasks_done integer;
  v_unlocked boolean;
  v_done boolean;
  v_module record;
begin
  -- student_can_access_section(...) is course-scoped for modular units.
  perform set_config('app.current_course_id', p_course_id::text, true);

  -- Fail closed unless the student is a member of this concrete course/unit pair.
  if not exists (
    select 1
      from public.course_memberships cm
      join public.course_modules m on m.course_id = cm.course_id
     where cm.course_id = p_course_id
       and cm.student_id = p_student_sub
       and m.unit_id = p_unit_id
  ) then
    return false;
  end if;

  select um.id
    into v_target_module_id
    from public.unit_modules um
    join public.units u on u.id = um.unit_id
   where um.unit_id = p_unit_id
     and um.section_id = p_section_id
     and u.unit_type = 'modular'
   limit 1;
  if v_target_module_id is null then
    return false;
  end if;

  select coalesce(jsonb_object_agg(done_rows.section_id, done_rows.tasks_done), '{}'::jsonb)
    into v_section_tasks_done
    from (
      select ls.section_id::text as section_id,
             count(distinct ls.task_id)::int as tasks_done
        from public.learning_submissions ls
       where ls.course_id = p_course_id
         and ls.student_sub = p_student_sub
         and (ls.kind <> 'h5p' or ls.score_raw = ls.score_max)
       group by ls.section_id
    ) as done_rows;

  for v_module in
    select um.id as module_id,
           um.section_id as section_id,
           greatest(coalesce(um.required_prereq_count, 0), 0)::int as required_prereq_count,
           greatest(coalesce(us.tasks_total, 0), 0)::int as tasks_total
      from public.unit_modules um
      join public.unit_sections us on us.id = um.section_id
      join public.unit_phases p on p.id = um.phase_id
     where um.unit_id = p_unit_id
     order by p.position asc, um.position_in_phase asc, um.id asc
  loop
    select coalesce(array_agg(e.from_module_id order by e.from_module_id), array[]::uuid[])
      into v_incoming_ids
      from public.unit_module_edges e
     where e.unit_id = p_unit_id
       and e.to_module_id = v_module.module_id;

    v_prereq_required := least(
      greatest(v_module.required_prereq_count, 0),
      coalesce(array_length(v_incoming_ids, 1), 0)
    );

    v_prereq_done := 0;
    if coalesce(array_length(v_incoming_ids, 1), 0) > 0 then
      foreach v_incoming_id in array v_incoming_ids loop
        if coalesce((v_done_by_module ->> v_incoming_id::text)::boolean, false) then
          v_prereq_done := v_prereq_done + 1;
        end if;
      end loop;
    end if;

    v_unlocked := (v_prereq_required = 0) or (v_prereq_done >= v_prereq_required);

    v_tasks_total := greatest(coalesce(v_module.tasks_total, 0), 0);
    v_raw_tasks_done := coalesce((v_section_tasks_done ->> v_module.section_id::text)::integer, 0);
    if v_tasks_total > 0 then
      v_raw_tasks_done := least(v_raw_tasks_done, v_tasks_total);
    else
      v_raw_tasks_done := 0;
    end if;

    v_done := v_unlocked and (v_tasks_total = 0 or v_raw_tasks_done >= v_tasks_total);
    v_done_by_module := v_done_by_module || jsonb_build_object(v_module.module_id::text, v_done);

    if v_module.module_id = v_target_module_id then
      return v_unlocked or v_done;
    end if;
  end loop;

  return false;
end;
$$;

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
  with _ctx as (
    select set_config('app.current_course_id', p_course_id::text, true) as _
  ),
  candidate as (
    select
      t.id as task_id,
      t.section_id,
      t.unit_id,
      u.unit_type,
      m.id as course_module_id
    from _ctx
    join public.course_memberships cm
      on cm.course_id = p_course_id
     and cm.student_id = p_student_sub
    join public.course_modules m
      on m.course_id = p_course_id
    join public.unit_tasks t
      on t.id = p_task_id
     and t.unit_id = m.unit_id
    join public.units u
      on u.id = t.unit_id
    limit 1
  )
  select exists (
    select 1
      from candidate c
     where (
       c.unit_type = 'linear'
       and exists (
         select 1
           from public.module_section_releases r
          where r.course_module_id = c.course_module_id
            and r.section_id = c.section_id
            and coalesce(r.visible, false) = true
       )
     )
     or (
       c.unit_type = 'modular'
       and public.modular_section_is_open_or_done_for_student(
         p_student_sub,
         p_course_id,
         c.unit_id,
         c.section_id
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
  with _ctx as (
    select set_config('app.current_course_id', p_course_id::text, true) as _
  ),
  candidate as (
    select
      t.id as task_id,
      t.section_id,
      t.unit_id,
      t.kind,
      t.h5p_content_id,
      t.max_attempts,
      t.criteria,
      u.unit_type,
      m.id as course_module_id
    from _ctx
    join public.course_memberships cm
      on cm.course_id = p_course_id
     and cm.student_id = p_student_sub
    join public.course_modules m
      on m.course_id = p_course_id
    join public.unit_tasks t
      on t.id = p_task_id
     and t.unit_id = m.unit_id
    join public.units u
      on u.id = t.unit_id
    limit 1
  )
  select
    c.task_id,
    c.section_id,
    c.unit_id,
    c.kind,
    c.h5p_content_id,
    c.max_attempts,
    c.criteria
  from candidate c
  where (
    c.unit_type = 'linear'
    and exists (
      select 1
      from public.module_section_releases r
      where r.course_module_id = c.course_module_id
        and r.section_id = c.section_id
        and coalesce(r.visible, false) = true
    )
  )
  or (
    c.unit_type = 'modular'
    and public.modular_section_is_open_or_done_for_student(
      p_student_sub,
      p_course_id,
      c.unit_id,
      c.section_id
    )
  )
  limit 1;
$$;

revoke all on function public.get_task_metadata_for_student(text, uuid, uuid) from public;
grant execute on function public.get_task_metadata_for_student(text, uuid, uuid) to gustav_limited;

revoke all on function public.modular_section_is_open_or_done_for_student(text, uuid, uuid, uuid) from public;
grant execute on function public.modular_section_is_open_or_done_for_student(text, uuid, uuid, uuid) to gustav_limited;

set check_function_bodies = on;
