-- Temporary public policy for section_materials debugging
-- WARNING: Only for debugging! Must be removed after problem is solved!

CREATE POLICY "temp_public_select_section_materials" 
ON storage.objects 
FOR SELECT 
TO public 
USING (bucket_id = 'section_materials');

-- Comment: This policy allows everyone (including ANON) access to section_materials
-- This helps us test if the problem is RLS-related or something else