-- Fix remaining foreign key constraints after task type separation
-- Problem: mastery_log, student_mastery_progress, and mastery_submission still reference old 'task' table
-- Solution: Update all FK constraints to reference 'task_base' instead

-- 1. Fix mastery_log foreign key
ALTER TABLE mastery_log 
DROP CONSTRAINT IF EXISTS mastery_log_task_id_fkey;

ALTER TABLE mastery_log 
ADD CONSTRAINT mastery_log_task_id_fkey 
FOREIGN KEY (task_id) 
REFERENCES task_base(id) 
ON DELETE CASCADE;

-- 2. Fix student_mastery_progress foreign key  
ALTER TABLE student_mastery_progress 
DROP CONSTRAINT IF EXISTS student_mastery_progress_task_id_fkey;

ALTER TABLE student_mastery_progress 
ADD CONSTRAINT student_mastery_progress_task_id_fkey 
FOREIGN KEY (task_id) 
REFERENCES task_base(id) 
ON DELETE CASCADE;

-- 3. Fix mastery_submission foreign key
ALTER TABLE mastery_submission 
DROP CONSTRAINT IF EXISTS mastery_submission_task_id_fkey;

ALTER TABLE mastery_submission 
ADD CONSTRAINT mastery_submission_task_id_fkey 
FOREIGN KEY (task_id) 
REFERENCES task_base(id) 
ON DELETE CASCADE;

-- Note: All task IDs are preserved in task_base, so no data migration needed
-- This maintains referential integrity with the new table structure