-- Hardening constraints for learning_submissions (generated via supabase migration new)

set check_function_bodies = off;

do $$
begin
  -- Enforce Idempotency-Key length ≤ 64
  if not exists (
    select 1 from pg_constraint
    where conname = 'learning_submissions_idempotency_key_len'
  ) then
    alter table public.learning_submissions
      add constraint learning_submissions_idempotency_key_len
      check (idempotency_key is null or char_length(idempotency_key) <= 64) not valid;
    alter table public.learning_submissions
      validate constraint learning_submissions_idempotency_key_len;
  end if;

  -- Text kind requires text_body and forbids file fields
  if not exists (
    select 1 from pg_constraint
    where conname = 'learning_submissions_text_kind'
  ) then
    alter table public.learning_submissions
      add constraint learning_submissions_text_kind
      check (
        kind <> 'text' or (
          text_body is not null and
          storage_key is null and mime_type is null and size_bytes is null and sha256 is null
        )
      ) not valid;
    alter table public.learning_submissions
      validate constraint learning_submissions_text_kind;
  end if;

  -- Image kind requires storage fields and forbids text_body
  if not exists (
    select 1 from pg_constraint
    where conname = 'learning_submissions_image_kind'
  ) then
    alter table public.learning_submissions
      add constraint learning_submissions_image_kind
      check (
        kind <> 'image' or (
          text_body is null and
          storage_key is not null and
          mime_type in ('image/jpeg', 'image/png') and
          size_bytes is not null and size_bytes > 0 and
          sha256 ~ '^[0-9a-f]{64}$'
        )
      ) not valid;
    alter table public.learning_submissions
      validate constraint learning_submissions_image_kind;
  end if;
end
$$;

set check_function_bodies = on;
