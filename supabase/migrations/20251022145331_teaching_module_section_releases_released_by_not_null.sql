-- Teaching (Unterrichten) — Strengthen section release auditing
-- Make released_by NOT NULL with a safe backfill for legacy rows.

-- Backfill existing rows where released_by is NULL
update public.module_section_releases
set released_by = 'system'
where released_by is null;

-- Enforce NOT NULL at schema level
alter table public.module_section_releases
  alter column released_by set not null;
