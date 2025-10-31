-- Dev bootstrap: create an environment-specific DB login for the app
--
-- Why: The application role `gustav_limited` is NOLOGIN by design. We need a
-- per-environment login role that inherits its privileges without committing
-- credentials into migrations or source control.
--
-- Usage (DEV/CI only):
--   export APP_DB_USER=gustav_app
--   export APP_DB_PASSWORD=CHANGE_ME_DEV
--   psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -v ON_ERROR_STOP=1 \
--     -f scripts/dev/create_login_user.sql
--
-- Notes:
-- - Run as a superuser (e.g., postgres) on your local dev database.
-- - Re-running is safe; the script updates the password if the role exists.
-- - Never commit real secrets. For staging/production, provision the login
--   role out-of-band via your secret management process.

\set app_user `echo "$APP_DB_USER"`
\set app_pass `echo "$APP_DB_PASSWORD"`

do $$
declare
  v_user text := :'app_user';
  v_pass text := :'app_pass';
begin
  -- Validate inputs
  if coalesce(v_user, '') = '' or coalesce(v_pass, '') = '' then
    raise exception 'APP_DB_USER/APP_DB_PASSWORD must be set in the environment';
  end if;

  if exists (select 1 from pg_roles where rolname = v_user) then
    execute format('alter role %I with login password %L in role gustav_limited', v_user, v_pass);
  else
    execute format('create role %I login password %L in role gustav_limited', v_user, v_pass);
  end if;
end$$;
