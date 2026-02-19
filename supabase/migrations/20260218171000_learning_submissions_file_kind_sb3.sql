-- Learning: allow SB3 file submissions in learning_submissions constraints.
--
-- Why:
--   Scratch tasks are SB3 upload-only. The submissions table currently restricts
--   kind='file' to PDFs only (mime_type='application/pdf'). We extend this to
--   also accept Scratch SB3 archives (application/x.scratch.sb3).

alter table if exists public.learning_submissions
  drop constraint if exists learning_submissions_file_kind;

alter table if exists public.learning_submissions
  add constraint learning_submissions_file_kind
  check (
    kind <> 'file' or (
      storage_key is not null and
      mime_type in ('application/pdf', 'application/x.scratch.sb3') and
      size_bytes between 1 and 10485760 and
      sha256 ~ '^[0-9a-f]{64}$'
    )
  );

