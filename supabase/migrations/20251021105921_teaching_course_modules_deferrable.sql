-- Adjust course_modules position constraint to be deferrable for transactional reorders

alter table public.course_modules
  drop constraint if exists course_modules_course_id_position_key;

alter table public.course_modules
  add constraint course_modules_course_id_position_key
    unique (course_id, position) deferrable initially immediate;
