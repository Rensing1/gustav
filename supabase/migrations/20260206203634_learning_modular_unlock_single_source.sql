-- Learning: define a single SQL source for modular unlock states.
--
-- Why:
--   Unlock/done semantics existed in both Python and SQL. This migration
--   introduces one shared SQL function that computes per-module states and
--   makes the boolean helper delegate to it.
--
-- Result:
--   - new function: get_modular_unit_module_states_for_student(...)
--   - modular_section_is_open_or_done_for_student(...) delegates to it
--   - execute rights explicitly hardened (no PUBLIC execute)

set check_function_bodies = off;

create or replace function public.get_modular_unit_module_states_for_student(
  p_student_sub text,
  p_course_id uuid,
  p_unit_id uuid
)
returns table (
  module_id uuid,
  section_id uuid,
  required_prereq_count integer,
  prereq_required integer,
  prereq_done integer,
  tasks_total integer,
  tasks_done integer,
  status text
)
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
  v_section_tasks_done jsonb := '{}'::jsonb;
  v_done_by_module jsonb := '{}'::jsonb;
  v_incoming_by_to jsonb := '{}'::jsonb;
  v_incoming_ids_json jsonb := '[]'::jsonb;
  v_incoming_id_text text;
  v_incoming_count integer;
  v_req_cfg integer;
  v_prereq_required integer;
  v_prereq_done integer;
  v_tasks_total integer;
  v_tasks_done integer;
  v_unlocked boolean;
  v_done boolean;
  v_module record;
begin
  perform set_config('app.current_course_id', p_course_id::text, true);

  -- Fail closed for non-members / wrong course-unit relation / non-modular units.
  if not exists (
    select 1
      from public.course_memberships cm
      join public.course_modules m on m.course_id = cm.course_id
     where cm.course_id = p_course_id
       and cm.student_id = p_student_sub
       and m.unit_id = p_unit_id
  ) then
    return;
  end if;

  if not exists (
    select 1
      from public.units u
     where u.id = p_unit_id
       and u.unit_type = 'modular'
  ) then
    return;
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

  select coalesce(
           jsonb_object_agg(edge_rows.to_module_id, edge_rows.from_module_ids),
           '{}'::jsonb
         )
    into v_incoming_by_to
    from (
      select e.to_module_id::text as to_module_id,
             to_jsonb(array_agg(e.from_module_id::text order by e.from_module_id)) as from_module_ids
        from public.unit_module_edges e
       where e.unit_id = p_unit_id
       group by e.to_module_id
    ) as edge_rows;

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
    v_incoming_ids_json := coalesce(v_incoming_by_to -> v_module.module_id::text, '[]'::jsonb);
    v_incoming_count := coalesce(jsonb_array_length(v_incoming_ids_json), 0);
    v_req_cfg := greatest(coalesce(v_module.required_prereq_count, 0), 0);

    v_prereq_required := least(v_req_cfg, v_incoming_count);
    v_prereq_done := 0;
    if v_incoming_count > 0 then
      for v_incoming_id_text in
        select value
          from jsonb_array_elements_text(v_incoming_ids_json) as t(value)
      loop
        if coalesce((v_done_by_module ->> v_incoming_id_text)::boolean, false) then
          v_prereq_done := v_prereq_done + 1;
        end if;
      end loop;
    end if;

    v_unlocked := (v_prereq_required = 0) or (v_prereq_done >= v_prereq_required);

    v_tasks_total := greatest(coalesce(v_module.tasks_total, 0), 0);
    v_tasks_done := coalesce((v_section_tasks_done ->> v_module.section_id::text)::integer, 0);
    if v_tasks_total > 0 then
      v_tasks_done := least(v_tasks_done, v_tasks_total);
    else
      v_tasks_done := 0;
    end if;

    v_done := v_unlocked and (v_tasks_total = 0 or v_tasks_done >= v_tasks_total);
    v_done_by_module := v_done_by_module || jsonb_build_object(v_module.module_id::text, v_done);

    module_id := v_module.module_id;
    section_id := v_module.section_id;
    required_prereq_count := v_req_cfg;
    prereq_required := v_prereq_required;
    prereq_done := v_prereq_done;
    tasks_total := v_tasks_total;
    tasks_done := v_tasks_done;
    status := case
      when v_done then 'done'
      when v_unlocked then 'open'
      else 'locked'
    end;

    return next;
  end loop;
end;
$$;

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
  v_status text;
begin
  perform set_config('app.current_course_id', p_course_id::text, true);

  select s.status
    into v_status
    from public.get_modular_unit_module_states_for_student(
      p_student_sub,
      p_course_id,
      p_unit_id
    ) s
   where s.section_id = p_section_id
   limit 1;

  return coalesce(v_status in ('open', 'done'), false);
end;
$$;

revoke all on function public.get_modular_unit_module_states_for_student(text, uuid, uuid) from public;
grant execute on function public.get_modular_unit_module_states_for_student(text, uuid, uuid) to gustav_limited;

revoke all on function public.modular_section_is_open_or_done_for_student(text, uuid, uuid, uuid) from public;
grant execute on function public.modular_section_is_open_or_done_for_student(text, uuid, uuid, uuid) to gustav_limited;

set check_function_bodies = on;
