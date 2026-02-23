-- Learning: allow MakeCode HEX file submissions in learning_submissions constraints.
--
-- Why:
--   Calliope tasks are HEX upload-only. The submissions table restricts
--   kind='file' to PDFs and Scratch SB3 archives; we extend it to also accept
--   MakeCode HEX (application/x.makecode.hex).

alter table if exists public.learning_submissions
  drop constraint if exists learning_submissions_file_kind;

alter table if exists public.learning_submissions
  add constraint learning_submissions_file_kind
  check (
    kind <> 'file' or (
      storage_key is not null and
      mime_type in ('application/pdf', 'application/x.scratch.sb3', 'application/x.makecode.hex') and
      size_bytes between 1 and 10485760 and
      sha256 ~ '^[0-9a-f]{64}$'
    )
  );

