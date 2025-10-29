-- Apply missing course_modules and module_section_releases from CSV inputs
-- Usage:
--   psql $SERVICE_ROLE_DSN -v modules_csv=/path/to/modules.csv -v releases_csv=/path/to/releases.csv -f docs/migration/sql/apply_modules_and_releases.sql
-- modules.csv columns: course_id,unit_id
-- releases.csv columns: course_id,unit_id,section_id

\set ON_ERROR_STOP on

-- Working tables (unlogged, dropped at end)
create unlogged table if not exists public.__tmp_modules (course_id uuid, unit_id uuid);
create unlogged table if not exists public.__tmp_releases (course_id uuid, unit_id uuid, section_id uuid);
truncate table public.__tmp_modules, public.__tmp_releases;

\copy public.__tmp_modules (course_id, unit_id) from :'modules_csv' with (format csv, header true);
\copy public.__tmp_releases (course_id, unit_id, section_id) from :'releases_csv' with (format csv, header true);

-- Insert missing course_modules with sequential positions
with next_pos as (
  select course_id, coalesce(max(position),0) as maxp
  from public.course_modules
  group by course_id
), new_pairs as (
  select t.course_id, t.unit_id
  from public.__tmp_modules t
  left join public.course_modules m on m.course_id = t.course_id and m.unit_id = t.unit_id
  where m.id is null
), numbered as (
  select np.course_id,
         np.unit_id,
         row_number() over (partition by np.course_id order by np.unit_id) as rn
  from new_pairs np
), ins as (
  insert into public.course_modules (course_id, unit_id, position)
  select n.course_id, n.unit_id, n.rn + coalesce(p.maxp,0)
  from numbered n
  left join next_pos p on p.course_id = n.course_id
  on conflict (course_id, unit_id) do nothing
  returning 1
)
select 'modules_added' as k, count(*) as v from ins;

-- Insert missing releases (visible=true; released_by=teacher_id)
with modules as (
  select m.id as course_module_id, m.course_id, m.unit_id from public.course_modules m
), courses as (
  select id as course_id, teacher_id from public.courses
), keys as (
  select tr.course_id, tr.unit_id, tr.section_id, mo.course_module_id, c.teacher_id
  from public.__tmp_releases tr
  join modules mo on mo.course_id = tr.course_id and mo.unit_id = tr.unit_id
  join courses c on c.course_id = tr.course_id
), ins as (
  insert into public.module_section_releases (course_module_id, section_id, visible, released_at, released_by)
  select k.course_module_id, k.section_id, true, now(), k.teacher_id
  from keys k
  on conflict (course_module_id, section_id) do nothing
  returning 1
)
select 'releases_added' as k, count(*) as v from ins;

drop table if exists public.__tmp_modules;
drop table if exists public.__tmp_releases;

