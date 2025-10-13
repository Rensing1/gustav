-- Fix RLS policies that still reference the old 'task' table after task type separation
-- Problem: mastery_log and storage policies still use 'task' instead of 'task_base'
-- Solution: Update policy definitions to use task_base

-- 1. Fix mastery_log RLS policy for teachers
-- Drop existing policy
DROP POLICY IF EXISTS "Lehrer koennen die Log-Eintraege ihrer Schueler sehen" ON public.mastery_log;

-- Recreate with task_base reference
CREATE POLICY "Lehrer koennen die Log-Eintraege ihrer Schueler sehen" 
ON public.mastery_log FOR SELECT
USING (
  get_my_role() = 'teacher' AND
  EXISTS (
    SELECT 1 
    FROM public.course_student cs
    JOIN public.task_base t ON t.id = mastery_log.task_id  -- Changed from 'task' to 'task_base'
    JOIN public.unit_section us ON t.section_id = us.id
    JOIN public.course_learning_unit_assignment clua ON us.unit_id = clua.unit_id
    WHERE cs.student_id = mastery_log.user_id
      AND cs.course_id = clua.course_id
      AND public.is_teacher_in_course(auth.uid(), cs.course_id)
  )
);

-- Note: Other policies appear to be working correctly with the views
-- Storage policies would need similar updates if they contain task references