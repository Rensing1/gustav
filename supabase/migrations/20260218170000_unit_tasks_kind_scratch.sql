-- Teaching/Learning: extend unit_tasks.kind enum check to include Scratch tasks.
--
-- Why:
--   Scratch tasks use Task.kind='scratch' and require SB3 upload-only submissions.
--
-- Notes:
--   We keep the column type as TEXT (MVP) and enforce allowed values via a
--   CHECK constraint, consistent with existing migrations.

alter table public.unit_tasks
  drop constraint if exists unit_tasks_kind_check;

alter table public.unit_tasks
  add constraint unit_tasks_kind_check
  check (kind in ('native', 'h5p', 'visual', 'scratch'));

