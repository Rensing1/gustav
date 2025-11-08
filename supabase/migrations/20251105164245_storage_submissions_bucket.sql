-- Storage — Provision `submissions` bucket (private)
--
-- Why:
--   Unify bucket provisioning with `materials` by creating `submissions`
--   deterministically via migrations. Keep buckets private; clients access
--   via signed URLs only.
--
-- Behavior:
--   - Idempotent: inserts only when `storage.buckets` exists and the bucket
--     is absent.
--   - No-ops on stacks without Supabase `storage` schema.

begin;

do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'storage'
      and table_name = 'buckets'
      and column_name = 'public'
  ) then
    insert into storage.buckets (id, name, public)
    select 'submissions', 'submissions', false
    where not exists (
      select 1 from storage.buckets where id = 'submissions'
    );
  end if;
end$$;

commit;
