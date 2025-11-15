-- Storage — ensure legacy learning bucket exists (backward compatibility)
--
-- Why:
--   Deployments prior to the LEARNING_STORAGE_BUCKET rename still use
--   LEARNING_SUBMISSIONS_BUCKET=learning-submissions. The backend now reads
--   both env vars, but Supabase must contain the referenced bucket so that
--   legacy values continue to work without manual intervention.
--
-- Behavior:
--   - Idempotently creates the `learning-submissions` bucket (private) if the
--     Supabase storage schema is present.
--   - Leaves existing `submissions` bucket untouched.

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
    select 'learning-submissions', 'learning-submissions', false
     where not exists (
       select 1 from storage.buckets where id = 'learning-submissions'
     );
  end if;
end$$;

commit;
