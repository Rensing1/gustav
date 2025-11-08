-- Add role column to course_memberships for membership-type checks
alter table if exists public.course_memberships
    add column if not exists role text not null default 'student';

-- Ensure future inserts default to 'student'
alter table if exists public.course_memberships
    alter column role set default 'student';

-- Backfill existing rows to the default in case column existed but was nullable
update public.course_memberships set role = 'student' where role is null;
