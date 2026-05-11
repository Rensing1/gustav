-- Persistent opaque CLI tokens for teacher authoring workflows.
-- Raw token values are shown once by the API and are never stored here.

create extension if not exists pgcrypto;

create table if not exists public.cli_tokens (
    id uuid primary key default gen_random_uuid(),
    user_sub text not null,
    label text not null check (char_length(trim(label)) between 1 and 80),
    token_hash text not null unique,
    scopes text[] not null check (
        cardinality(scopes) > 0
        and scopes <@ array['read', 'write', 'delete']::text[]
    ),
    created_at timestamptz not null default now(),
    expires_at timestamptz not null check (expires_at > created_at),
    last_used_at timestamptz,
    revoked_at timestamptz
);

create index if not exists idx_cli_tokens_user_sub on public.cli_tokens (user_sub);
create index if not exists idx_cli_tokens_active_lookup on public.cli_tokens (id, revoked_at, expires_at);

alter table public.cli_tokens enable row level security;

-- Deny by default for browser/db clients; the backend service role verifies hashes.
revoke all on public.cli_tokens from anon;
revoke all on public.cli_tokens from authenticated;
