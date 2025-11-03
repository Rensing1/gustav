do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'gustav_web') then
        create role gustav_web noinherit nologin;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'gustav_operator') then
        create role gustav_operator noinherit nologin;
    end if;
end;
$$;

-- Learning worker health probe helper
create or replace function public.learning_worker_health_probe()
returns table (
    check_name text,
    status text,
    detail text
)
language plpgsql
security definer
set search_path = public
as $$
declare
    has_worker_role boolean;
    visible_jobs bigint;
begin
    select exists(select 1 from pg_roles where rolname = 'gustav_worker') into has_worker_role;
    select count(*) into visible_jobs
      from public.learning_submission_jobs as jobs
     where jobs.status = 'queued'
       and jobs.visible_at <= now();

    check_name := 'db_role';
    status := case when has_worker_role then 'ok' else 'failed' end;
    detail := case when has_worker_role then null else 'gustav_worker role not available' end;
    return next;

    check_name := 'queue_visibility';
    status := 'ok';
    detail := 'visible_jobs=' || visible_jobs;
    return next;
end;
$$;

comment on function public.learning_worker_health_probe() is
    'Returns diagnostic info for the learning worker health endpoint';

grant execute on function public.learning_worker_health_probe() to gustav_web, gustav_operator;
