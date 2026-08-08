-- Teaching: add practice modules and teacher-only model solutions.
--
-- Why:
--   Practice modules are graph nodes with stricter content rules. Enforcing
--   those rules in PostgreSQL keeps API, CLI and future import paths aligned.

set check_function_bodies = off;
set search_path = public, pg_temp;

alter table public.unit_modules
  add column if not exists module_kind text not null default 'learning';

alter table public.unit_modules
  drop constraint if exists unit_modules_module_kind_check;
alter table public.unit_modules
  add constraint unit_modules_module_kind_check
  check (module_kind in ('learning', 'practice'));

alter table public.unit_tasks
  add column if not exists model_solution_md text null;

create or replace function public.practice_module_kind_immutable()
returns trigger
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
begin
  if new.module_kind is distinct from old.module_kind then
    raise exception 'module_kind is immutable'
      using errcode = 'check_violation';
  end if;
  return new;
end;
$$;

drop trigger if exists trg_practice_module_kind_immutable on public.unit_modules;
create trigger trg_practice_module_kind_immutable
before update of module_kind on public.unit_modules
for each row execute function public.practice_module_kind_immutable();

create or replace function public.practice_edge_source_guard()
returns trigger
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
begin
  if exists (
    select 1
      from public.unit_modules module
     where module.id = new.from_module_id
       and module.module_kind = 'practice'
  ) then
    raise exception 'practice_module_outgoing_edge'
      using errcode = 'check_violation';
  end if;
  return new;
end;
$$;

drop trigger if exists trg_practice_edge_source_guard on public.unit_module_edges;
create trigger trg_practice_edge_source_guard
before insert or update on public.unit_module_edges
for each row execute function public.practice_edge_source_guard();

create or replace function public.practice_material_guard()
returns trigger
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
begin
  if exists (
    select 1
      from public.unit_modules module
     where module.section_id = new.section_id
       and module.module_kind = 'practice'
  ) then
    raise exception 'practice_module_material_forbidden'
      using errcode = 'check_violation';
  end if;
  return new;
end;
$$;

drop trigger if exists trg_practice_material_guard on public.unit_materials;
create trigger trg_practice_material_guard
before insert or update of section_id on public.unit_materials
for each row execute function public.practice_material_guard();

create or replace function public.practice_task_guard()
returns trigger
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
begin
  if not exists (
    select 1
      from public.unit_modules module
     where module.section_id = new.section_id
       and module.module_kind = 'practice'
  ) then
    return new;
  end if;

  if new.kind not in ('native', 'h5p') then
    raise exception 'practice_task_kind_not_supported'
      using errcode = 'check_violation';
  end if;

  if new.due_at is not null or new.max_attempts is not null then
    raise exception 'practice_schedule_fields_forbidden'
      using errcode = 'check_violation';
  end if;

  if new.kind = 'native' and (
    cardinality(new.criteria) < 1
    or new.teacher_context_md is null
    or length(btrim(new.teacher_context_md)) = 0
    or new.model_solution_md is null
    or length(btrim(new.model_solution_md)) = 0
  ) then
    raise exception 'practice_fields_required'
      using errcode = 'check_violation';
  end if;

  return new;
end;
$$;

drop trigger if exists trg_practice_task_guard on public.unit_tasks;
create trigger trg_practice_task_guard
before insert or update of section_id, kind, criteria, teacher_context_md,
  model_solution_md, due_at, max_attempts on public.unit_tasks
for each row execute function public.practice_task_guard();

set check_function_bodies = on;
