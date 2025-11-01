-- Learning submissions: allow PDF files and enforce 10 MB size limit
set search_path = public, pg_temp;

do $$
begin
  -- Relax kind constraint to include 'file'
  if exists (
    select 1 from pg_constraint
    where conrelid = 'public.learning_submissions'::regclass
      and conname = 'learning_submissions_kind_check'
  ) then
    alter table public.learning_submissions
      drop constraint learning_submissions_kind_check;
  end if;
exception when others then
  -- Defensive: continue if constraint missing or insufficient privileges
  raise notice 'Skipping drop of learning_submissions_kind_check: %', sqlerrm;
end $$;

alter table public.learning_submissions
  add constraint learning_submissions_kind_check
  check (kind in ('text','image','file'));

-- Enforce 10 MiB max size for binary submissions (defense-in-depth)
do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.learning_submissions'::regclass
      and conname = 'learning_submissions_size_limit_check'
  ) then
    alter table public.learning_submissions
      add constraint learning_submissions_size_limit_check
      check (size_bytes is null or (size_bytes >= 1 and size_bytes <= 10485760));
  end if;
end $$;


