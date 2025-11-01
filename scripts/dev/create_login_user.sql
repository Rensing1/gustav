-- Dev bootstrap: create an environment-specific DB login for the app
--
-- Why: The application role `gustav_limited` is NOLOGIN by design. We need a
-- per-environment login role that inherits its privileges without committing
-- credentials into migrations or source control.
--
-- Usage (DEV/CI only):
--   export APP_DB_USER=gustav_app
--   export APP_DB_PASSWORD=CHANGE_ME_DEV
--   psql -h 127.0.0.1 -p 54322 -U postgres -d postgres \
--     -v app_user="$APP_DB_USER" -v app_pass="$APP_DB_PASSWORD" \
--     -f scripts/dev/create_login_user.sql
--
-- Notes:
-- - Run as a superuser (e.g., postgres) on your local dev database.
-- - Re-running is safe; the script updates the password if the role exists.
-- - Never commit real secrets. For staging/production, provision the login
--   role out-of-band via your secret management process.

-- Accept variables via psql -v OR fallback to environment variables.
-- This avoids passing secrets on the process command line by allowing
-- APP_DB_USER/APP_DB_PASSWORD from the environment.
\if :{?app_user}
\else
  \set app_user :ENV.APP_DB_USER
\endif
\if :{?app_pass}
\else
  \set app_pass :ENV.APP_DB_PASSWORD
\endif

-- Final guard: require both values to be present after fallback.
\if :{?app_user}
\else
  \echo 'ERROR: app_user not provided. Set APP_DB_USER env or pass -v app_user=...'
  \quit 1
\endif
\if :{?app_pass}
\else
  \echo 'ERROR: app_pass not provided. Set APP_DB_PASSWORD env or pass -v app_pass=...'
  \quit 1
\endif

select set_config('app.bootstrap_user', :'app_user', false);
select set_config('app.bootstrap_pass', :'app_pass', false);

do $$
declare
  v_user text := current_setting('app.bootstrap_user', true);
  v_pass text := current_setting('app.bootstrap_pass', true);
begin
  -- Validate inputs
  if coalesce(v_user, '') = '' or coalesce(v_pass, '') = '' then
    raise exception 'APP_DB_USER/APP_DB_PASSWORD must be set in the environment';
  end if;

  if exists (select 1 from pg_roles where rolname = v_user) then
    execute format('alter role %I with login password %L', v_user, v_pass);
  else
    execute format('create role %I login password %L in role gustav_limited', v_user, v_pass);
  end if;
end$$;

select format('grant gustav_limited to %I', current_setting('app.bootstrap_user', true))
\gexec

select set_config('app.bootstrap_user', null, true);
select set_config('app.bootstrap_pass', null, true);
