-- Modular learning units — edge-safe moves (modules + phases).
--
-- Why:
--   `public.unit_module_edges` are validated on INSERT, but a later reorder/move
--   of `public.unit_modules` (or a reorder of `public.unit_phases`) could make
--   an existing edge invalid without firing any trigger.
--
-- Strategy:
--   Add DEFERRABLE CONSTRAINT TRIGGERs that validate affected edges at commit
--   time:
--     - when a module changes phase/position
--     - when a phase changes its position
--
-- Result:
--   Teacher-side drag&drop operations fail-closed: moves that would break the
--   "same-phase right / next-phase only" rules are rejected with a CHECK
--   VIOLATION (surfaced as `edge_constraint_violation` in the Teaching API).

set check_function_bodies = off;
set search_path = public, pg_temp;

-- Shared validator used by both constraint triggers.
create or replace function public.validate_unit_module_edges_for_unit(
  p_unit_id uuid,
  p_module_id uuid default null
)
returns void
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
  unit_type text;
  violation_exists boolean;
begin
  -- Sanity: unit must exist and be modular.
  select u.unit_type into unit_type
    from public.units u
   where u.id = p_unit_id;
  if unit_type is null then
    raise exception 'unit % does not exist', p_unit_id using errcode = 'foreign_key_violation';
  end if;
  if unit_type <> 'modular' then
    raise exception 'unit % is not modular', p_unit_id using errcode = 'check_violation';
  end if;

  -- Validate either:
  --   - all edges of the unit (p_module_id is null), or
  --   - edges where the moved module participates (incoming + outgoing).
  select exists (
    with edge_view as (
      select
        e.from_module_id,
        e.to_module_id,
        um_from.phase_id as from_phase_id,
        um_from.position_in_phase as from_pos_in_phase,
        um_to.phase_id as to_phase_id,
        um_to.position_in_phase as to_pos_in_phase,
        p_from.position as from_phase_pos,
        p_to.position as to_phase_pos
      from public.unit_module_edges e
      join public.unit_modules um_from
        on um_from.id = e.from_module_id
       and um_from.unit_id = e.unit_id
      join public.unit_modules um_to
        on um_to.id = e.to_module_id
       and um_to.unit_id = e.unit_id
      join public.unit_phases p_from
        on p_from.id = um_from.phase_id
       and p_from.unit_id = e.unit_id
      join public.unit_phases p_to
        on p_to.id = um_to.phase_id
       and p_to.unit_id = e.unit_id
      where e.unit_id = p_unit_id
        and (
          p_module_id is null
          or e.from_module_id = p_module_id
          or e.to_module_id = p_module_id
        )
    )
    select 1
      from edge_view
     where
       -- Same-phase edges must go "right": strictly increasing position.
       (from_phase_id = to_phase_id and not (from_pos_in_phase < to_pos_in_phase))
       or
       -- Cross-phase edges must target the next phase (from_pos+1).
       (from_phase_id <> to_phase_id and not (to_phase_pos = from_phase_pos + 1))
     limit 1
  ) into violation_exists;

  if violation_exists then
    raise exception 'edge_constraint_violation' using errcode = 'check_violation';
  end if;
end;
$$;

-- 1) Module move/reorder must not invalidate existing edges.
create or replace function public.trg_unit_modules_validate_edges_on_update()
returns trigger
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
begin
  perform public.validate_unit_module_edges_for_unit(new.unit_id, new.id);
  return new;
end;
$$;

drop trigger if exists trg_unit_modules_validate_edges_on_update on public.unit_modules;
create constraint trigger trg_unit_modules_validate_edges_on_update
after update of phase_id, position_in_phase on public.unit_modules
deferrable initially deferred
for each row execute function public.trg_unit_modules_validate_edges_on_update();

-- 2) Phase reorder must not invalidate cross-phase edges.
create or replace function public.trg_unit_phases_validate_edges_on_update()
returns trigger
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
begin
  perform public.validate_unit_module_edges_for_unit(new.unit_id, null);
  return new;
end;
$$;

drop trigger if exists trg_unit_phases_validate_edges_on_update on public.unit_phases;
create constraint trigger trg_unit_phases_validate_edges_on_update
after update of position on public.unit_phases
deferrable initially deferred
for each row execute function public.trg_unit_phases_validate_edges_on_update();

set check_function_bodies = on;
