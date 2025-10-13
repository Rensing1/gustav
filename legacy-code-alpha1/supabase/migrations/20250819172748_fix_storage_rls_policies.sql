-- Fix storage RLS policies for section_materials
-- Remove old policies and create new ones with better error handling

-- Drop the temporary debug policy
DROP POLICY IF EXISTS "temp_public_select_section_materials" ON storage.objects;

-- Drop existing problematic policies
DROP POLICY IF EXISTS "allow_select_for_enrolled_users" ON storage.objects;
DROP POLICY IF EXISTS "allow_select_for_unit_creators" ON storage.objects;

-- Create improved policies with better auth.uid() handling

-- Policy for students: Check if they are enrolled in the unit from the file path
CREATE POLICY "students_can_select_enrolled_materials" 
ON storage.objects 
FOR SELECT 
TO authenticated
USING (
  bucket_id = 'section_materials' 
  AND auth.uid() IS NOT NULL
  AND EXISTS (
    SELECT 1 FROM profiles 
    WHERE id = auth.uid() 
    AND role = 'student'
  )
  AND is_enrolled_in_unit(auth.uid(), get_unit_id_from_path(name))
);

-- Policy for teachers: Check if they created the unit from the file path  
CREATE POLICY "teachers_can_select_created_materials"
ON storage.objects
FOR SELECT 
TO authenticated
USING (
  bucket_id = 'section_materials'
  AND auth.uid() IS NOT NULL  
  AND EXISTS (
    SELECT 1 FROM profiles 
    WHERE id = auth.uid() 
    AND role = 'teacher'
  )
  AND is_creator_of_unit(auth.uid(), get_unit_id_from_path(name))
);

-- Keep other policies for insert/update/delete as they were
-- (they are already working for material upload)