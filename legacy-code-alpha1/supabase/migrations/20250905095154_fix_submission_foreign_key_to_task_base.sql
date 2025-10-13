-- Fix submission foreign key after task type separation
-- Problem: submission.task_id still references the old 'task' table which no longer exists
-- Solution: Update foreign key to reference 'task_base' instead

-- Drop the old foreign key constraint
ALTER TABLE submission 
DROP CONSTRAINT IF EXISTS submission_task_id_fkey;

-- Add new foreign key constraint to task_base
ALTER TABLE submission 
ADD CONSTRAINT submission_task_id_fkey 
FOREIGN KEY (task_id) 
REFERENCES task_base(id) 
ON DELETE CASCADE;

-- Note: This maintains referential integrity while working with the new table structure
-- All task IDs are preserved in task_base, so no data migration is needed