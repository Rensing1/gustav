-- Teaching (Unterrichten) — Course management schema
-- Notes:
-- - Uses pgcrypto for gen_random_uuid()
-- - Adds courses and course_memberships tables
-- - Enables RLS (server accesses via service role only)

create extension if not exists pgcrypto;

-- Shared trigger to maintain updated_at
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- Courses table
create table if not exists public.courses (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  subject text null,
  grade_level text null,
  term text null,
  teacher_id text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_courses_teacher on public.courses(teacher_id);

drop trigger if exists trg_courses_updated_at on public.courses;
create trigger trg_courses_updated_at
before update on public.courses
for each row execute function public.set_updated_at();

-- Course memberships
create table if not exists public.course_memberships (
  course_id uuid not null references public.courses(id) on delete cascade,
  student_id text not null,
  created_at timestamptz not null default now(),
  primary key (course_id, student_id)
);

create index if not exists idx_course_memberships_student on public.course_memberships(student_id);

-- Security: enable RLS; policies are defined at the application layer (service role only)
alter table public.courses enable row level security;
alter table public.course_memberships enable row level security;
