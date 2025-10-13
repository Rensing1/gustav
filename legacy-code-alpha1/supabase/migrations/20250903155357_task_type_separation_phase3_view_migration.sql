-- Phase 3: Task Type Separation - View Migration to New Structure
-- Updates views to read from new table structure instead of old task table

-- Drop existing views that point to old task table
DROP VIEW IF EXISTS all_regular_tasks;
DROP VIEW IF EXISTS all_mastery_tasks;

-- Recreate views to use new table structure (task_base + regular_tasks/mastery_tasks)
-- Views maintain same column structure as original task table for backward compatibility

-- Regular tasks view: Combines task_base with regular_tasks
CREATE VIEW all_regular_tasks AS
SELECT 
    tb.id,
    tb.section_id,
    tb.instruction,
    tb.task_type,
    rt.order_in_section,
    tb.criteria,
    tb.assessment_criteria,
    tb.solution_hints,
    false as is_mastery,  -- Always false for regular tasks
    rt.max_attempts,
    tb.created_at,
    tb.updated_at
FROM task_base tb
JOIN regular_tasks rt ON tb.id = rt.task_id;

-- Mastery tasks view: Combines task_base with mastery_tasks  
CREATE VIEW all_mastery_tasks AS
SELECT 
    tb.id,
    tb.section_id,
    tb.instruction,
    tb.task_type,
    1 as order_in_section,  -- Default order for mastery tasks (not used in UI)
    tb.criteria,
    tb.assessment_criteria,
    tb.solution_hints,
    true as is_mastery,     -- Always true for mastery tasks
    NULL as max_attempts,   -- No attempt limits for mastery tasks
    tb.created_at,
    tb.updated_at
FROM task_base tb
JOIN mastery_tasks mt ON tb.id = mt.task_id;

-- Comments for documentation
COMMENT ON VIEW all_regular_tasks IS 'Phase 3: View showing regular tasks from new table structure (task_base + regular_tasks). Maintains backward compatibility with old task table structure.';
COMMENT ON VIEW all_mastery_tasks IS 'Phase 3: View showing mastery tasks from new table structure (task_base + mastery_tasks). Maintains backward compatibility with old task table structure.';

-- Verify data consistency between old and new views
DO $$
DECLARE
    old_regular_count integer;
    new_regular_count integer;
    old_mastery_count integer;
    new_mastery_count integer;
BEGIN
    -- Count regular tasks in old structure
    SELECT COUNT(*) INTO old_regular_count 
    FROM task 
    WHERE is_mastery = false OR is_mastery IS NULL;
    
    -- Count regular tasks in new structure  
    SELECT COUNT(*) INTO new_regular_count 
    FROM all_regular_tasks;
    
    -- Count mastery tasks in old structure
    SELECT COUNT(*) INTO old_mastery_count 
    FROM task 
    WHERE is_mastery = true;
    
    -- Count mastery tasks in new structure
    SELECT COUNT(*) INTO new_mastery_count 
    FROM all_mastery_tasks;
    
    RAISE NOTICE 'Phase 3 View Migration Validation:';
    RAISE NOTICE '  Regular tasks - Old: %, New: %', old_regular_count, new_regular_count;
    RAISE NOTICE '  Mastery tasks - Old: %, New: %', old_mastery_count, new_mastery_count;
    
    -- Verify counts match
    IF old_regular_count != new_regular_count THEN
        RAISE EXCEPTION 'MIGRATION FAILED: Regular task count mismatch - Old: %, New: %', old_regular_count, new_regular_count;
    END IF;
    
    IF old_mastery_count != new_mastery_count THEN
        RAISE EXCEPTION 'MIGRATION FAILED: Mastery task count mismatch - Old: %, New: %', old_mastery_count, new_mastery_count;
    END IF;
    
    RAISE NOTICE 'SUCCESS: View migration completed. All task counts match between old and new structure.';
END;
$$;