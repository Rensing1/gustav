-- Harden execute privileges for edge validator helper.
--
-- Why:
--   `public.validate_unit_module_edges_for_unit(...)` is called from
--   constraint triggers and must not be executable by PUBLIC.
--
-- Result:
--   Execute privilege is explicitly restricted to `gustav_limited`.

set check_function_bodies = off;
set search_path = public, pg_temp;

revoke all
  on function public.validate_unit_module_edges_for_unit(uuid, uuid)
  from public;

grant execute
  on function public.validate_unit_module_edges_for_unit(uuid, uuid)
  to gustav_limited;

set check_function_bodies = on;
