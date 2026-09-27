-- Teaching Live: owner-scoped practice aggregates for one paginated learner page.
--
-- The helper deliberately returns counts instead of a final presentation
-- label. PostgreSQL owns access and due-state semantics; the framework-
-- independent Teaching read model owns the small, documented status priority.

set check_function_bodies = off;

create or replace function public.get_unit_live_practice_aggregates_for_owner(
  p_owner_sub text,
  p_course_id uuid,
  p_unit_id uuid,
  p_student_subs text[]
)
returns table (
  student_sub text,
  module_id uuid,
  section_id uuid,
  module_title text,
  module_position integer,
  access_status text,
  task_count integer,
  due_tasks_count integer,
  secure_tasks_count integer,
  partial_tasks_count integer,
  insufficient_tasks_count integer,
  latest_activity_at timestamptz,
  next_due_at timestamptz
)
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
  with owner_course as (
    select course.id
      from public.courses course
     where course.id = p_course_id
       and course.teacher_id = p_owner_sub
       and course.teacher_id = coalesce(current_setting('app.current_sub', true), '')
       and exists (
         select 1
           from public.course_modules course_module
          where course_module.course_id = course.id
            and course_module.unit_id = p_unit_id
       )
  ), requested_students as (
    select distinct requested.student_sub
      from unnest(coalesce(p_student_subs, array[]::text[])) requested(student_sub)
  ), member_students as (
    select requested.student_sub
      from requested_students requested
      join public.course_memberships membership
        on membership.course_id = p_course_id
       and membership.student_id = requested.student_sub
      join owner_course on true
  ), accessible_modules as (
    select member.student_sub,
           module_state.module_id,
           module_state.section_id,
           module_state.status as access_status
      from member_students member
      cross join lateral public.get_modular_unit_module_states_for_student(
        member.student_sub,
        p_course_id,
        p_unit_id,
        true
      ) module_state
     where module_state.module_kind = 'practice'
  ), practice_tasks as (
    select module.id as module_id,
           module.section_id,
           section.title as module_title,
           section.position as module_position,
           task.id as task_id
      from public.unit_modules module
      join public.unit_sections section on section.id = module.section_id
      left join public.unit_tasks task on task.section_id = section.id
     where module.unit_id = p_unit_id
       and module.module_kind = 'practice'
  )
  select access.student_sub,
         access.module_id,
         access.section_id,
         max(task.module_title) as module_title,
         max(task.module_position)::integer as module_position,
         access.access_status,
         count(task.task_id)::integer as task_count,
         count(task.task_id) filter (
           where access.access_status in ('open', 'done')
             and (state.task_id is null or state.due_at <= statement_timestamp())
         )::integer as due_tasks_count,
         count(task.task_id) filter (
           where access.access_status in ('open', 'done')
             and state.due_at > statement_timestamp()
             and state.last_classification = 'secure'
         )::integer as secure_tasks_count,
         count(task.task_id) filter (
           where access.access_status in ('open', 'done')
             and state.due_at > statement_timestamp()
             and state.last_classification = 'partial'
         )::integer as partial_tasks_count,
         count(task.task_id) filter (
           where access.access_status in ('open', 'done')
             and state.due_at > statement_timestamp()
             and state.last_classification = 'insufficient'
         )::integer as insufficient_tasks_count,
         max(state.last_attempt_at) as latest_activity_at,
         min(state.due_at) filter (where state.due_at > statement_timestamp()) as next_due_at
    from accessible_modules access
    join practice_tasks task on task.module_id = access.module_id
    left join public.learning_practice_states state
      on state.course_id = p_course_id
     and state.student_sub = access.student_sub
     and state.task_id = task.task_id
   group by access.student_sub,
            access.module_id,
            access.section_id,
            access.access_status
   order by access.student_sub, max(task.module_position), access.module_id;
$$;

revoke all on function public.get_unit_live_practice_aggregates_for_owner(text, uuid, uuid, text[]) from public;
grant execute on function public.get_unit_live_practice_aggregates_for_owner(text, uuid, uuid, text[]) to gustav_limited;

set check_function_bodies = on;
