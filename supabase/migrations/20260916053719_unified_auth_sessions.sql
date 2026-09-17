-- Additive cutover: old app sessions are never promoted to token sessions.
alter table public.app_sessions
    add column access_token text,
    add column refresh_token text,
    add column access_expires_at timestamptz,
    add column refresh_version bigint not null default 0,
    add column refresh_locked_until timestamptz,
    add column retry_after timestamptz;

create table public.auth_flows (
    state_hash text primary key,
    browser_hash text not null,
    mode text not null check (mode in ('login', 'register', 'password', 'continue', 'logout')),
    redirect_path text,
    code_verifier text not null,
    nonce text not null,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null default now() + interval '15 minutes'
);
create index auth_flows_browser_idx on public.auth_flows(browser_hash, created_at);
create index auth_flows_expiry_idx on public.auth_flows(expires_at);
alter table public.auth_flows enable row level security;
revoke all on public.auth_flows from public, anon, authenticated;
