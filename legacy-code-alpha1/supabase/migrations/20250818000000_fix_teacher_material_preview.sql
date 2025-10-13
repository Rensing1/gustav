-- Migration: Allow teachers to preview materials in their own units
-- Problem: Teachers get 404 errors when trying to preview materials they uploaded
-- Solution: Add SELECT policy for unit creators (matching existing INSERT/UPDATE/DELETE policies)

-- Add SELECT policy for teachers who created the unit
CREATE POLICY "allow_select_for_unit_creators" ON storage.objects
FOR SELECT
USING (
    bucket_id = 'section_materials' AND
    public.is_teacher(auth.uid()) AND
    public.is_creator_of_unit(auth.uid(), public.get_unit_id_from_path(name))
);

-- Note: This complements the existing "allow_select_for_enrolled_users" policy
-- Now both enrolled students AND unit creators can view materials