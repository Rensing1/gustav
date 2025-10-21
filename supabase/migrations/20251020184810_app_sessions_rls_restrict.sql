-- Restrict app_sessions access to service roles only (no gustav_limited access)

revoke select, insert, update, delete on public.app_sessions from gustav_limited;
drop policy if exists app_sessions_rw on public.app_sessions;

-- Service role (postgres) retains access; security relies on privileged DSN.
create policy app_sessions_service_rw on public.app_sessions
  for all to postgres
  using (true)
  with check (true);
