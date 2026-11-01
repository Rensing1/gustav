-- Private mutable drafts are independent of submissions and their AI pipeline.
create table public.learning_task_drafts (
  student_sub text not null,
  course_id uuid not null references public.courses(id) on delete cascade,
  task_id uuid not null references public.unit_tasks(id) on delete cascade,
  text_body text not null check (char_length(text_body) <= 65536),
  updated_at timestamptz not null default clock_timestamp(),
  primary key (student_sub, course_id, task_id),
  foreign key (course_id, student_sub)
    references public.course_memberships(course_id, student_id) on delete cascade
);
create index learning_task_drafts_course_idx on public.learning_task_drafts(course_id);
create index learning_task_drafts_task_idx on public.learning_task_drafts(task_id);

-- Invoker security keeps existing task visibility/RLS as the source of truth.
create function public.learning_task_draft_access(p_student_sub text, p_course_id uuid, p_task_id uuid)
returns boolean language sql stable security invoker
set search_path = pg_catalog, public
as $$
  select p_student_sub = coalesce(current_setting('app.current_sub', true), '')
    and public.is_active_course_member(p_course_id, p_student_sub)
    and public.check_task_visible_to_student(p_student_sub, p_course_id, p_task_id)
    and exists (
      select 1 from public.unit_tasks t
      where t.id = p_task_id and t.kind = 'native'
        and not exists (
          select 1 from public.unit_modules m
          where m.section_id = t.section_id and m.module_kind = 'practice'
        )
    );
$$;
revoke all on function public.learning_task_draft_access(text, uuid, uuid) from public;
grant execute on function public.learning_task_draft_access(text, uuid, uuid) to gustav_limited;

alter table public.learning_task_drafts enable row level security;
grant select, insert, update on public.learning_task_drafts to gustav_limited;
create policy learning_task_drafts_own on public.learning_task_drafts
  for all to gustav_limited
  using (public.learning_task_draft_access(student_sub, course_id, task_id))
  with check (public.learning_task_draft_access(student_sub, course_id, task_id));
