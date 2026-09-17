-- Apply after accepting the shared-session cutover and deciding against fallback.
-- This removes authentication state only; accounts and learning data are untouched.
drop table public.bff_sessions;
delete from public.app_sessions where access_token is null;
