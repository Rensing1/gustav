-- Phase 1: Task Type Separation - Views for Migration
-- These views enable a gradual migration from is_mastery flag to separate tables
-- RLS security is inherited from the underlying task table

-- View for Regular Tasks (non-Mastery tasks)
CREATE VIEW all_regular_tasks AS
SELECT 
    id,
    section_id,
    instruction,
    task_type,
    order_in_section,
    criteria,
    assessment_criteria,
    solution_hints,
    is_mastery,
    max_attempts,
    created_at,
    updated_at
FROM task 
WHERE is_mastery = false OR is_mastery IS NULL;

-- View for Mastery Tasks (Wissensfestiger)
CREATE VIEW all_mastery_tasks AS
SELECT 
    id,
    section_id,
    instruction,
    task_type,
    order_in_section,
    criteria,
    assessment_criteria,
    solution_hints,
    is_mastery,
    max_attempts,
    created_at,
    updated_at
FROM task 
WHERE is_mastery = true;

-- Comments for documentation
COMMENT ON VIEW all_regular_tasks IS 'View for regular tasks (is_mastery=false or NULL) - Phase 1 of Task Type Separation. RLS inherited from task table.';
COMMENT ON VIEW all_mastery_tasks IS 'View for Wissensfestiger tasks (is_mastery=true) - Phase 1 of Task Type Separation. RLS inherited from task table.';