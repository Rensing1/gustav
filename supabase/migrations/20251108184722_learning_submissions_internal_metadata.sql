-- learning_submissions: store extraction artifacts internally (JSONB)
set check_function_bodies = off;

alter table if exists public.learning_submissions
    add column if not exists internal_metadata jsonb not null default '{}'::jsonb;

comment on column public.learning_submissions.internal_metadata is
    'Internal-only metadata (e.g., extracted page keys) that is never exposed via the public API.';
