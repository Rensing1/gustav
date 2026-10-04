-- Teaching: allow download-only program and OpenDocument material files.
-- The bucket remains private; application authorization still controls access.

begin;

do $$
begin
  if exists (
    select 1
      from information_schema.columns
     where table_schema = 'storage'
       and table_name = 'buckets'
       and column_name = 'allowed_mime_types'
  ) then
    update storage.buckets
       set public = false,
           allowed_mime_types = (
             select array_agg(distinct allowed_mime order by allowed_mime)
               from unnest(
                 coalesce(allowed_mime_types, array[]::text[])
                 || array[
                   'application/pdf',
                   'image/png',
                   'image/jpeg',
                   'text/html',
                   'application/x.scratch.sb3',
                   'application/x.makecode.hex',
                   'application/x.filius.fls',
                   'text/x-python',
                   'application/json',
                   'text/plain',
                   'application/vnd.oasis.opendocument.text',
                   'application/vnd.oasis.opendocument.spreadsheet',
                   'application/vnd.oasis.opendocument.presentation'
                 ]::text[]
               ) allowed_mime
           )
     where id = 'materials';
  end if;
end$$;

commit;
