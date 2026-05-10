-- Storage — Allow Filius `.fls` uploads in learning submission buckets
--
-- Why:
--   Filius tasks in GUSTAV use FLS upload-only submissions with MIME
--   `application/x.filius.fls`. Supabase Storage enforces per-bucket MIME
--   allowlists via `storage.buckets.allowed_mime_types`.
--
-- Behavior:
--   - Idempotent: updates only when the column exists and a supported bucket exists.
--   - No-ops on stacks without Supabase Storage schema.

begin;

do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'storage'
      and table_name = 'buckets'
      and column_name = 'allowed_mime_types'
  ) then
    update storage.buckets
       set allowed_mime_types = (
         select array_agg(distinct mime order by mime)
         from unnest(
           coalesce(allowed_mime_types, array[]::text[]) ||
           array[
             'application/pdf',
             'application/x.scratch.sb3',
             'application/x.makecode.hex',
             'application/x.filius.fls',
             'image/png',
             'image/jpeg'
           ]::text[]
         ) as mime
       )
     where id in ('submissions', 'learning-submissions');
  end if;
end$$;

commit;
