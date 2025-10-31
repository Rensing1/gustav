-- Security hardening: ensure the application role cannot be used to log in.
-- Context: A previous dev migration created `gustav_limited` with LOGIN and a
-- known password for local convenience. Shipping this into stage/prod is risky.
-- This migration makes the role NOLOGIN. Provision an environment-specific
-- LOGIN user outside of migrations, which inherits from `gustav_limited`.

set search_path = public, pg_temp;

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'gustav_limited') then
    -- Remove the ability to log in using this role.
    execute 'alter role gustav_limited NOLOGIN';
    -- Optional: add documentation for DBAs.
    perform 1;
  end if;
end
$$;

comment on role gustav_limited is
  'Application role with least privileges. NOLOGIN by design; use a separate environment-specific login role that is IN ROLE gustav_limited.';

