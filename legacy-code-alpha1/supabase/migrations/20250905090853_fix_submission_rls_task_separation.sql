-- Fix submission RLS policy after task type separation
-- Problem: The old policy references 'task' table which no longer exists after Phase 4 cleanup
-- Solution: Update to use task_base table which is the new source of truth

-- Drop the old policy that references the non-existent 'task' table
DROP POLICY IF EXISTS "Allow students to insert submission for visible tasks once" ON public.submission;

-- Create new policy that works with the task_base table structure
CREATE POLICY "Allow students to insert submission for visible tasks once"
  ON public.submission FOR INSERT
  WITH CHECK (
    get_my_role() = 'student' AND
    student_id = auth.uid() AND
    EXISTS (
      -- Check if student is allowed to view the task via task_base
      SELECT 1 FROM task_base tb
      WHERE tb.id = submission.task_id
      AND EXISTS (
        -- Check if student can see the section containing this task
        SELECT 1 FROM unit_section us
        JOIN learning_unit lu ON us.unit_id = lu.id
        JOIN course_learning_unit_assignment clua ON lu.id = clua.unit_id
        JOIN course_student cs ON clua.course_id = cs.course_id
        WHERE us.id = tb.section_id
        AND cs.student_id = auth.uid()
      )
    )
  );

-- Note: The UNIQUE constraint on (student_id, task_id, attempt_number) still handles the attempt limits
-- The actual attempt validation happens in the application layer (create_submission function)