-- Purpose: Remove the old unique constraint on (student_id, task_id) that prevents multiple submissions.
ALTER TABLE submission DROP CONSTRAINT IF EXISTS unique_student_task_submission;