-- Persistent Browser-BFF token sessions.
-- Keeps access/refresh tokens server-side and the browser cookie opaque.

create extension if not exists pgcrypto;

create table if not exists public.bff_sessions (
    session_id text primary key,
    access_token text not null,
    refresh_token text,
    id_token text not null,
    expires_at timestamptz not null
);

create index if not exists idx_bff_sessions_expires_at on public.bff_sessions (expires_at);

alter table public.bff_sessions enable row level security;

revoke all on public.bff_sessions from anon;
revoke all on public.bff_sessions from authenticated;
