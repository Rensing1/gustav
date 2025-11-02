-- Latest submission (with content) for owner (teacher)
--
-- Security: SECURITY DEFINER ensures teachers (owners) can retrieve latest
-- submissions for their course members without bypassing RLS as invokers.
-- The function validates course ownership and restricts by course_id, task_id,
-- and student_sub. It returns only the latest row by created_at.
set check_function_bodies = off;

create or replace function public.get_latest_submission_for_owner(
  p_owner_sub text,
  p_course_id uuid,
  p_task_id uuid,
  p_student_sub text
)
returns table (
  id uuid,
  task_id uuid,
  student_sub text,
  created_at timestamptz,
  completed_at timestamptz,
  kind text,
  text_body text,
  mime_type text,
  size_bytes integer,
  storage_key text
)
language sql
security definer
set search_path = public, pg_temp
as $$
  with owner as (
    select 1
      from public.courses c
     where c.id = p_course_id
       and c.teacher_id = p_owner_sub
  ), latest as (
    select ls.id,
           ls.task_id,
           ls.student_sub,
           ls.created_at,
           ls.completed_at,
           ls.kind::text,
           ls.text_body,
           ls.mime_type,
           ls.size_bytes,
           ls.storage_key
      from public.learning_submissions ls
     where ls.course_id = p_course_id
       and ls.task_id = p_task_id
       and ls.student_sub = p_student_sub
     order by ls.created_at desc
     limit 1
  )
  select l.id,
         l.task_id,
         l.student_sub,
         l.created_at,
         l.completed_at,
         l.kind,
         l.text_body,
         l.mime_type,
         l.size_bytes,
         l.storage_key
    from owner, latest l;
$$;

grant execute on function public.get_latest_submission_for_owner(text, uuid, uuid, text) to gustav_limited;

