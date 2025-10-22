-- Strengthen SHA-256 integrity check for file materials
-- Ensure hex-only (lowercase) 64-char values using a regex, not length alone.

begin;

alter table public.unit_materials
  drop constraint if exists unit_materials_file_fields_check;

alter table public.unit_materials
  add constraint unit_materials_file_fields_check
  check (
    case
      when kind = 'markdown' then
        storage_key is null
        and filename_original is null
        and mime_type is null
        and size_bytes is null
        and sha256 is null
      when kind = 'file' then
        storage_key is not null
        and filename_original is not null
        and mime_type is not null
        and size_bytes is not null
        and size_bytes > 0
        and sha256 is not null
        and sha256 ~ '^[0-9a-f]{64}$'
      else false
    end
  );

commit;
