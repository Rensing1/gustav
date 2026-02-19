-- Storage — Allow Scratch `.sb3` uploads in `submissions` bucket
--
-- Why:
--   Scratch tasks in GUSTAV use SB3 upload-only submissions with MIME
--   `application/x.scratch.sb3`. Supabase Storage enforces per-bucket MIME
--   allowlists via `storage.buckets.allowed_mime_types`. Existing stacks may
--   have the bucket configured for PDF/PNG/JPEG only, causing SB3 PUT uploads
--   to fail with `invalid_mime_type`.
--
-- Behavior:
--   - Idempotent: updates only when the column exists and the bucket exists.
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
       set allowed_mime_types = array[
         'application/pdf',
         'application/x.scratch.sb3',
         'image/png',
         'image/jpeg'
       ]
     where id = 'submissions';
  end if;
end$$;

commit;

