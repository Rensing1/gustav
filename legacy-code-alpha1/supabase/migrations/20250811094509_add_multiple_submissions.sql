-- Migration: Add multiple submissions support
-- Purpose: Allow students to submit tasks multiple times with configurable limits

-- 1. Add max_attempts to task table
ALTER TABLE task 
ADD COLUMN max_attempts INTEGER DEFAULT 1 
CHECK (max_attempts >= 1 AND max_attempts <= 10);

COMMENT ON COLUMN task.max_attempts IS 'Maximum number of submission attempts allowed for this task';

-- 2. Remove old unique constraint on submission
ALTER TABLE submission 
DROP CONSTRAINT IF EXISTS submission_student_id_task_id_key;

-- 3. Add attempt_number to submission table
ALTER TABLE submission 
ADD COLUMN attempt_number INTEGER NOT NULL DEFAULT 1
CHECK (attempt_number >= 1);

COMMENT ON COLUMN submission.attempt_number IS 'Submission attempt number (1, 2, 3, ...)';

-- 4. Add new unique constraint including attempt_number
ALTER TABLE submission 
ADD CONSTRAINT submission_student_task_attempt_unique 
UNIQUE (student_id, task_id, attempt_number);

-- 5. Create index for performance when querying submission history
CREATE INDEX idx_submission_student_task_attempt 
ON submission(student_id, task_id, attempt_number);

-- 6. Update RLS policies (no changes needed - existing policies still work)
-- Students can still only see their own submissions
-- Teachers can still see all submissions in their units
-- The attempt_number just adds another dimension to the data

-- 7. Create helper function to get submission count
CREATE OR REPLACE FUNCTION get_submission_count(p_student_id UUID, p_task_id UUID)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  RETURN (
    SELECT COUNT(*)
    FROM submission
    WHERE student_id = p_student_id 
    AND task_id = p_task_id
  );
END;
$$;

-- 8. Create helper function to check if student can submit
CREATE OR REPLACE FUNCTION can_submit_task(p_student_id UUID, p_task_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_max_attempts INTEGER;
  v_current_attempts INTEGER;
BEGIN
  -- Get max attempts for task
  SELECT max_attempts INTO v_max_attempts
  FROM task
  WHERE id = p_task_id;
  
  -- Get current attempt count
  v_current_attempts := get_submission_count(p_student_id, p_task_id);
  
  -- Return true if under limit
  RETURN v_current_attempts < v_max_attempts;
END;
$$;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION get_submission_count TO authenticated;
GRANT EXECUTE ON FUNCTION can_submit_task TO authenticated;