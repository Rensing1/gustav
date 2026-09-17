-- Keep claimed flows revocable while token I/O runs outside transactions.
alter table public.auth_flows add column claimed_at timestamptz;
-- Bind issued sessions to the flow browser, including undelivered cookies.
alter table public.app_sessions add column browser_hash text;
create index app_sessions_browser_idx on public.app_sessions(browser_hash);
