--supabase/migrations/20250811143000_add_rls_for_section_materials.sql

-- Helper function to check if a user has the 'teacher' role.
create or replace function public.is_teacher(p_user_id uuid)
returns boolean
language sql
security definer
stable
as $$
  select exists (
    select 1
    from public.profiles
    where id = p_user_id and role = 'teacher'::public.user_role
  );
$$;

-- Helper function to extract unit_id from a storage path.
create or replace function public.get_unit_id_from_path(p_path text)
returns uuid
language plpgsql
stable
as $$
declare
  v_unit_id_text text;
begin
  select (regexp_matches(p_path, 'unit_([a-f0-9\-]+)/'))[1] into v_unit_id_text;
  return v_unit_id_text::uuid;
exception
  when others then
    return null;
end;
$$;

-- Helper function to check if a user is enrolled in a course that contains the given unit.
create or replace function public.is_enrolled_in_unit(p_user_id uuid, p_unit_id uuid)
returns boolean
language sql
security definer
stable
as $$
  select exists (
    select 1
    from public.course_student cs
    join public.course_learning_unit_assignment clua on cs.course_id = clua.course_id
    where cs.student_id = p_user_id
    and clua.unit_id = p_unit_id
  );
$$;

-- Helper function to check if a user is the creator of a unit.
create or replace function public.is_creator_of_unit(p_user_id uuid, p_unit_id uuid)
returns boolean
language sql
security definer
stable
as $$
  select exists (
    select 1
    from public.learning_unit lu
    where lu.id = p_unit_id
    and lu.creator_id = p_user_id
  );
$$;

-- Create the storage bucket if it doesn't exist
insert into storage.buckets (id, name, public)
values ('section_materials', 'section_materials', false)
on conflict (id) do nothing;

-- RLS Policies for section_materials bucket

-- Drop existing policies if they exist, to ensure a clean slate.
DROP POLICY IF EXISTS "allow_select_for_enrolled_users" ON storage.objects;
DROP POLICY IF EXISTS "allow_insert_for_unit_creators" ON storage.objects;
DROP POLICY IF EXISTS "allow_update_for_unit_creators" ON storage.objects;
DROP POLICY IF EXISTS "allow_delete_for_unit_creators" ON storage.objects;

-- 1. Allow SELECT (read/download) for users enrolled in the unit's course
create policy "allow_select_for_enrolled_users" on storage.objects
for select
using (
    bucket_id = 'section_materials' and
    public.is_enrolled_in_unit(auth.uid(), public.get_unit_id_from_path(name))
);

-- 2. Allow INSERT for teachers who created the unit
create policy "allow_insert_for_unit_creators" on storage.objects
for insert
with check (
    bucket_id = 'section_materials' and
    public.is_teacher(auth.uid()) and
    public.is_creator_of_unit(auth.uid(), public.get_unit_id_from_path(name))
);

-- 3. Allow UPDATE for teachers who created the unit
create policy "allow_update_for_unit_creators" on storage.objects
for update
using (
    bucket_id = 'section_materials' and
    public.is_teacher(auth.uid()) and
    public.is_creator_of_unit(auth.uid(), public.get_unit_id_from_path(name))
);

-- 4. Allow DELETE for teachers who created the unit
create policy "allow_delete_for_unit_creators" on storage.objects
for delete
using (
    bucket_id = 'section_materials' and
    public.is_teacher(auth.uid()) and
    public.is_creator_of_unit(auth.uid(), public.get_unit_id_from_path(name))
);
