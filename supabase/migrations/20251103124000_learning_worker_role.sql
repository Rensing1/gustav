-- Migration: ensure dedicated worker role exists before queue/helper grants
set search_path = public, pg_temp;

do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'gustav_worker') then
        create role gustav_worker login password 'gustav-worker';
    end if;
end
$$;

alter role gustav_worker inherit;

grant usage on schema public to gustav_worker;
grant select on public.learning_submissions to gustav_worker;
grant select, update, delete on public.learning_submission_jobs to gustav_worker;
grant gustav_limited to gustav_worker;
