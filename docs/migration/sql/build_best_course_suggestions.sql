-- Build heuristic suggestions (Top‑1 per skipped submission) for courses and releases
-- Produces:
--   /tmp/modules_auto.csv  (course_id,unit_id)
--   /tmp/releases_auto.csv (course_id,unit_id,section_id)

\set ON_ERROR_STOP on
\t on
\a off

-- Use the latest run id
with run as (
  select id from public.import_audit_runs order by started_at_utc desc limit 1
), skipped as (
  select legacy_id::uuid as sub_id
  from public.import_audit_mappings, run
  where run_id=run.id and entity='legacy_submission' and status='skip' and reason='missing_course'
), s as (
  select st.* from staging.submissions st join skipped k on k.sub_id = st.id
), task_map as (
  select t.id as task_id, t.section_id, t.unit_id from public.unit_tasks t
), unit_titles as (
  select u.id as unit_id, lower(u.title) as unit_title from public.units u
), memberships as (
  select cm.student_id, cm.course_id, lower(c.title) as course_title, c.teacher_id
  from public.course_memberships cm
  join public.courses c on c.id = cm.course_id
), tokenized as (
  select s.id as submission_id, s.student_sub, s.task_id, tm.unit_id, tm.section_id,
         m.course_id, m.course_title, m.teacher_id,
         regexp_split_to_table(replace(ut.unit_title, '–', ' '), E'[^a-z0-9]+') as token
  from s
  join task_map tm on tm.task_id = s.task_id
  join unit_titles ut on ut.unit_id = tm.unit_id
  join memberships m on m.student_id = s.student_sub
), scored as (
  select submission_id, student_sub, task_id, unit_id, section_id, course_id, course_title, teacher_id,
         count(*) filter (where length(token)>=3) as score
  from tokenized
  group by 1,2,3,4,5,6,7,8
), ranked as (
  select *,
         rank() over (partition by submission_id order by score desc, course_title asc) as rnk,
         max(score) over (partition by submission_id) as max_score
  from scored
)
select submission_id, student_sub, task_id, unit_id, section_id, course_id, course_title, teacher_id, max_score
into temporary tmp_best
from ranked
where rnk = 1 and max_score >= 1;

-- Export CSVs
\copy (select distinct course_id, unit_id from tmp_best order by course_id, unit_id) to '/tmp/modules_auto.csv' with (format csv, header true)
\copy (select distinct course_id, unit_id, section_id from tmp_best order by course_id, unit_id, section_id) to '/tmp/releases_auto.csv' with (format csv, header true)

-- Quick counts
select (select count(*) from tmp_best) as suggestions,
       (select count(*) from (select distinct course_id, unit_id from tmp_best) x) as modules_pairs,
        (select count(*) from (select distinct course_id, unit_id, section_id from tmp_best) y) as release_triples;

