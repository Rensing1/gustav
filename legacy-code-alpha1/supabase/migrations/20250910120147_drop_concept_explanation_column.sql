-- Drop concept_explanation column from mastery_tasks table
-- This column is always NULL and not used in the UI
-- The solution_hints column from task_base should be used instead

-- First, we need to recreate the all_mastery_tasks view without concept_explanation
DROP VIEW IF EXISTS all_mastery_tasks CASCADE;

CREATE VIEW all_mastery_tasks AS
SELECT 
    t.*,
    mt.prompt,
    mt.difficulty_level,
    -- concept_explanation removed, use solution_hints from task_base instead
    mt.spaced_repetition_interval
FROM task_base t
JOIN mastery_tasks mt ON t.id = mt.task_id;

-- Grant the same permissions as before
GRANT SELECT ON all_mastery_tasks TO authenticated;

-- Now we can safely drop the column
ALTER TABLE mastery_tasks DROP COLUMN IF EXISTS concept_explanation;

-- Add comment to document the change
COMMENT ON TABLE mastery_tasks IS 'Mastery task specific attributes. Use solution_hints from task_base for explanations.';