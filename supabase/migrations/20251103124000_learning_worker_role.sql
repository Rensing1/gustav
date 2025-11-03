-- Migration: ensure dedicated worker role exists before queue/helper grants
set search_path = public, pg_temp;

do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'gustav_worker') then
        -- Security: avoid committing passwords in migrations. Create a role without
        -- password; deployments should set a secret password separately if LOGIN
        -- is required for a dedicated worker user.
        create role gustav_worker noinherit nologin;
    end if;
end
$$;

-- Keep inheritance enabled for role membership/privilege propagation
alter role gustav_worker inherit;

grant usage on schema public to gustav_worker;
grant select on public.learning_submissions to gustav_worker;
grant select, update, delete on public.learning_submission_jobs to gustav_worker;
grant gustav_limited to gustav_worker;
