-- Add mastery flag to tasks table
ALTER TABLE task ADD COLUMN is_mastery BOOLEAN DEFAULT FALSE;

-- Add comment for documentation
COMMENT ON COLUMN task.is_mastery IS 'Indicates if this task is a mastery/spaced repetition task (Wissensfestiger)';

-- Create index for performance when querying mastery tasks
CREATE INDEX idx_task_mastery ON task(is_mastery) WHERE is_mastery = TRUE;

-- Also create a compound index for course-based mastery queries
CREATE INDEX idx_task_section_mastery ON task(section_id, is_mastery) 
WHERE is_mastery = TRUE;