-- Teaching: extend unit_tasks with task kinds (native|h5p|visual)

alter table public.unit_tasks
  add column if not exists kind text not null default 'native',
  add column if not exists h5p_content_id text null,
  add column if not exists h5p_display_options jsonb not null default '{}'::jsonb;

alter table public.unit_tasks
  drop constraint if exists unit_tasks_kind_check;

alter table public.unit_tasks
  add constraint unit_tasks_kind_check
  check (kind in ('native', 'h5p', 'visual'));

