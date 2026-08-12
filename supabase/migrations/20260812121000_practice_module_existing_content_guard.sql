-- Teaching: reject practice modules that wrap incompatible existing content.

set search_path = public, pg_temp;

create or replace function public.practice_module_content_guard()
returns trigger
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
begin
  if new.module_kind <> 'practice' then
    return new;
  end if;

  if exists (
    select 1 from public.unit_materials material where material.section_id = new.section_id
  ) or exists (
    select 1
      from public.unit_tasks task
     where task.section_id = new.section_id
       and (
         task.kind not in ('native', 'h5p')
         or task.due_at is not null
         or task.max_attempts is not null
         or (
           task.kind = 'native'
           and (
             cardinality(task.criteria) < 1
             or nullif(btrim(task.teacher_context_md), '') is null
             or nullif(btrim(task.model_solution_md), '') is null
           )
         )
       )
  ) then
    raise exception 'practice_module_existing_content_invalid'
      using errcode = 'check_violation';
  end if;
  return new;
end;
$$;

drop trigger if exists trg_practice_module_content_guard on public.unit_modules;
create trigger trg_practice_module_content_guard
before insert or update of section_id, module_kind on public.unit_modules
for each row execute function public.practice_module_content_guard();
