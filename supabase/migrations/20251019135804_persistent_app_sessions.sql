-- Migration: persistent app sessions (privacy-first)
-- Generated via `supabase migration new persistent_app_sessions`

create extension if not exists pgcrypto;

create table if not exists public.app_sessions (
    session_id text primary key,
    sub text not null,
    roles jsonb not null,
    name text not null,
    id_token text,
    expires_at timestamptz not null
);

create index if not exists idx_app_sessions_sub on public.app_sessions (sub);
create index if not exists idx_app_sessions_expires_at on public.app_sessions (expires_at);

alter table public.app_sessions enable row level security;

-- Deny by default for anon/authenticated; service role will bypass RLS.
revoke all on public.app_sessions from anon;
revoke all on public.app_sessions from authenticated;
