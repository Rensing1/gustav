-- Teaching/Learning: extend unit_tasks.kind enum check to include Filius tasks.
--
-- Why:
--   Filius tasks use Task.kind='filius' and require FLS upload-only submissions.

alter table public.unit_tasks
  drop constraint if exists unit_tasks_kind_check;

alter table public.unit_tasks
  add constraint unit_tasks_kind_check
  check (kind in ('native', 'h5p', 'visual', 'scratch', 'calliope', 'filius'));
