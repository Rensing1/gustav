-- Harden unit_module_edges privileges by removing UPDATE access.
--
-- Why:
--   Edges are immutable by design (delete + insert workflow). UPDATE rights
--   and an UPDATE policy increase write surface without any functional need.
--
-- Result:
--   - gustav_limited no longer has UPDATE privilege on unit_module_edges
--   - unit_module_edges_update_author policy is removed

set check_function_bodies = off;
set search_path = public, pg_temp;

do $$
begin
  if to_regclass('public.unit_module_edges') is null then
    raise notice 'skip hardening: table public.unit_module_edges does not exist';
    return;
  end if;

  execute 'revoke update on table public.unit_module_edges from gustav_limited';
  execute 'drop policy if exists unit_module_edges_update_author on public.unit_module_edges';
end
$$;

set check_function_bodies = on;
