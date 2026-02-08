-- Learning: optimize modular unlock helper by preloading edges once per unit.
--
-- Why:
--   `modular_section_is_open_or_done_for_student(...)` was querying
--   `unit_module_edges` inside the module loop (N+1 pattern).
--   This migration pre-aggregates incoming edges per target module once and
--   reuses the in-memory map during the unlock walk.

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
  v_incoming_by_to jsonb := '{}'::jsonb;
  v_incoming_ids_json jsonb := '[]'::jsonb;
  v_incoming_id_text text;
  v_incoming_count integer;
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

  -- Preload incoming edges per target module once (avoid N+1 edge lookups).
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

    v_prereq_required := least(
      greatest(v_module.required_prereq_count, 0),
      v_incoming_count
    );

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

set check_function_bodies = on;
