-- Restore original storage policies and remove complex ones
-- This reverts to the simpler policies that were working before

-- Drop the complex policies that were failing
DROP POLICY IF EXISTS "students_can_select_enrolled_materials" ON storage.objects;
DROP POLICY IF EXISTS "teachers_can_select_created_materials" ON storage.objects;

-- Restore the original policies from the dashboard
-- These were working before our session isolation changes

CREATE POLICY "allow_select_for_enrolled_users" 
ON storage.objects 
FOR SELECT 
TO authenticated 
USING (
  bucket_id = 'section_materials' 
  AND is_enrolled_in_unit(auth.uid(), get_unit_id_from_path(name))
);

CREATE POLICY "allow_select_for_unit_creators" 
ON storage.objects 
FOR SELECT 
TO authenticated 
USING (
  bucket_id = 'section_materials' 
  AND is_teacher(auth.uid()) 
  AND is_creator_of_unit(auth.uid(), get_unit_id_from_path(name))
);
