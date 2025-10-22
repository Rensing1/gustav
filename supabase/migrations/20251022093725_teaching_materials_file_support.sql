-- Teaching (Unterrichten) — Datei-Materialien Support (Iteration 1b)
-- Extends unit_materials with file metadata and introduces upload_intents table.

begin;

-- Add kind discriminator and file-specific metadata columns.
alter table public.unit_materials
  add column if not exists kind text not null default 'markdown';

alter table public.unit_materials
  add constraint unit_materials_kind_check
  check (kind in ('markdown', 'file'));

alter table public.unit_materials
  add column if not exists storage_key text;

alter table public.unit_materials
  add column if not exists filename_original text;

alter table public.unit_materials
  add column if not exists mime_type text;

alter table public.unit_materials
  add column if not exists size_bytes integer;

alter table public.unit_materials
  add column if not exists sha256 text;

alter table public.unit_materials
  add column if not exists alt_text text;

-- Ensure file metadata completeness depending on material kind.
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
        and char_length(sha256) = 64
      else false
    end
  );

-- Enforce unique storage key when present.
create unique index if not exists unit_materials_storage_key_idx
  on public.unit_materials (storage_key)
  where storage_key is not null;

-- Upload intents table for presigned uploads.
create table if not exists public.upload_intents (
  id uuid primary key default gen_random_uuid(),
  material_id uuid not null,
  unit_id uuid not null references public.units(id) on delete cascade,
  section_id uuid not null references public.unit_sections(id) on delete cascade,
  author_id text not null,
  storage_key text not null,
  filename text not null,
  mime_type text not null,
  size_bytes integer not null check (size_bytes > 0),
  expires_at timestamptz not null,
  consumed_at timestamptz null,
  created_at timestamptz not null default now(),
  unique (material_id),
  unique (storage_key)
);

create index if not exists upload_intents_author_idx on public.upload_intents(author_id);
create index if not exists upload_intents_section_idx on public.upload_intents(section_id, material_id);

-- Row Level Security setup for upload intents.
alter table public.upload_intents enable row level security;

grant select, insert, update, delete on public.upload_intents to gustav_limited;

do $$
begin
  if exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'upload_intents'
  ) then
    drop policy if exists upload_intents_select_author on public.upload_intents;
    drop policy if exists upload_intents_insert_author on public.upload_intents;
    drop policy if exists upload_intents_update_author on public.upload_intents;
    drop policy if exists upload_intents_delete_author on public.upload_intents;
  end if;
end$$;

create policy upload_intents_select_author on public.upload_intents
  for select to gustav_limited
  using (author_id = coalesce(current_setting('app.current_sub', true), ''));

create policy upload_intents_insert_author on public.upload_intents
  for insert to gustav_limited
  with check (author_id = coalesce(current_setting('app.current_sub', true), ''));

create policy upload_intents_update_author on public.upload_intents
  for update to gustav_limited
  using (author_id = coalesce(current_setting('app.current_sub', true), ''))
  with check (author_id = coalesce(current_setting('app.current_sub', true), ''));

create policy upload_intents_delete_author on public.upload_intents
  for delete to gustav_limited
  using (author_id = coalesce(current_setting('app.current_sub', true), ''));

-- Optional: bucket provisioning for private materials storage (if storage schema present)
do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'storage'
      and table_name = 'buckets'
      and column_name = 'public'
  ) then
    insert into storage.buckets (id, name, public)
    select 'materials', 'materials', false
    where not exists (select 1 from storage.buckets where id = 'materials');
  end if;
end$$;

commit;
