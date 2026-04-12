-- Split Browser-BFF token lifetime from BFF session lifetime.
-- Why:
--   The old schema stored only a single expires_at timestamp, which behaved
--   like an access-token expiry and caused the frontend session bridge to die
--   long before a normal classroom session ended.

alter table public.bff_sessions
    add column if not exists access_token_expires_at timestamptz,
    add column if not exists session_expires_at timestamptz;

update public.bff_sessions
set
    access_token_expires_at = coalesce(access_token_expires_at, expires_at),
    session_expires_at = coalesce(session_expires_at, now() + interval '24 hours');

alter table public.bff_sessions
    alter column access_token_expires_at set not null,
    alter column session_expires_at set not null;

create index if not exists idx_bff_sessions_session_expires_at
    on public.bff_sessions (session_expires_at);
