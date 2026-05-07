-- Learning: allow Filius FLS file submissions in learning_submissions constraints.
--
-- Why:
--   Filius tasks are FLS upload-only. The submissions table restricts
--   kind='file' to known upload MIME types; we extend it to also accept
--   Filius FLS (application/x.filius.fls).

alter table if exists public.learning_submissions
  drop constraint if exists learning_submissions_file_kind;

alter table if exists public.learning_submissions
  add constraint learning_submissions_file_kind
  check (
    kind <> 'file' or (
      storage_key is not null and
      mime_type in (
        'application/pdf',
        'application/x.scratch.sb3',
        'application/x.makecode.hex',
        'application/x.filius.fls'
      ) and
      size_bytes between 1 and 10485760 and
      sha256 ~ '^[0-9a-f]{64}$'
    )
  );
