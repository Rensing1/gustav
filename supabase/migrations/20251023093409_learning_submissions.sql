-- Learning (Lernen) — Submissions table (MVP)
-- Stores immutable student submissions with attempt numbering and analysis stub payloads.

create extension if not exists pgcrypto;

create table if not exists public.learning_submissions (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references public.courses(id) on delete cascade,
  task_id uuid not null references public.unit_tasks(id) on delete cascade,
  student_sub text not null,
  kind text not null check (kind in ('text', 'image')),
  text_body text null,
  storage_key text null,
  mime_type text null,
  size_bytes integer null check (size_bytes is null or size_bytes > 0),
  sha256 text null check (sha256 ~ '^[0-9a-f]{64}$'),
  attempt_nr integer not null,
  analysis_status text not null default 'pending' check (analysis_status in ('pending', 'completed', 'error')),
  analysis_json jsonb null,
  feedback_md text null,
  error_code text null,
  idempotency_key text null,
  created_at timestamptz not null default now(),
  completed_at timestamptz null,
  unique (course_id, task_id, student_sub, attempt_nr)
);

create index if not exists idx_learning_submissions_course_task_sub
  on public.learning_submissions(course_id, task_id, student_sub);

create index if not exists idx_learning_submissions_created_at
  on public.learning_submissions(created_at desc);

create index if not exists idx_learning_submissions_student_task_created
  on public.learning_submissions(student_sub, task_id, created_at desc);

alter table public.learning_submissions enable row level security;

grant select, insert on public.learning_submissions to gustav_limited;

create unique index if not exists idx_learning_submissions_idempotency_key
  on public.learning_submissions(course_id, task_id, student_sub, idempotency_key)
  where idempotency_key is not null;
