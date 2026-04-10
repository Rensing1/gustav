-- Concern box entries for learner feedback tied to one course.

create extension if not exists pgcrypto;

create table if not exists public.concern_box_entries (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references public.courses(id) on delete cascade,
  student_sub text not null,
  message_text text not null check (length(btrim(message_text)) > 0),
  anonymous boolean not null default true,
  created_at timestamptz not null default now(),
  archived_at timestamptz null,
  archived_by text null
);

create index if not exists idx_concern_box_entries_course_created
  on public.concern_box_entries(course_id, created_at desc);

create index if not exists idx_concern_box_entries_student_created
  on public.concern_box_entries(student_sub, created_at desc);

create index if not exists idx_concern_box_entries_open_created
  on public.concern_box_entries(created_at desc)
  where archived_at is null;

alter table public.concern_box_entries enable row level security;

grant select, insert, update on public.concern_box_entries to gustav_limited;

drop policy if exists concern_box_entries_insert_member on public.concern_box_entries;
create policy concern_box_entries_insert_member on public.concern_box_entries
  for insert to gustav_limited
  with check (
    student_sub = coalesce(current_setting('app.current_sub', true), '')
    and exists (
      select 1
        from public.course_memberships cm
       where cm.course_id = concern_box_entries.course_id
         and cm.student_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

drop policy if exists concern_box_entries_select_owner on public.concern_box_entries;
create policy concern_box_entries_select_owner on public.concern_box_entries
  for select to gustav_limited
  using (
    exists (
      select 1
        from public.courses c
       where c.id = concern_box_entries.course_id
         and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

drop policy if exists concern_box_entries_update_owner on public.concern_box_entries;
create policy concern_box_entries_update_owner on public.concern_box_entries
  for update to gustav_limited
  using (
    exists (
      select 1
        from public.courses c
       where c.id = concern_box_entries.course_id
         and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
    )
  )
  with check (
    exists (
      select 1
        from public.courses c
       where c.id = concern_box_entries.course_id
         and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );
