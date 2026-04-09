set search_path = public, pg_temp;

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
    visible_jobs bigint;
begin
    select count(*) into visible_jobs
      from public.learning_submission_jobs as jobs
     where jobs.status = 'queued'
       and jobs.visible_at <= now();

    check_name := 'queue_visibility';
    status := 'ok';
    detail := 'visible_jobs=' || visible_jobs;
    return next;
end;
$$;

comment on function public.learning_worker_health_probe() is
    'Returns queue visibility diagnostics for the learning worker health endpoint';

revoke all on function public.learning_worker_health_probe() from public;
grant execute on function public.learning_worker_health_probe() to gustav_web, gustav_operator, gustav_limited;
