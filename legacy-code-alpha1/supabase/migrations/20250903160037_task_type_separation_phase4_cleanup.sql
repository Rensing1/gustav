-- Phase 4: Task Type Separation - Cleanup
-- Remove old columns from task table and finalize migration

-- Create backup of current task table data before cleanup
CREATE TABLE IF NOT EXISTS task_backup_phase4 AS 
SELECT * FROM task;

COMMENT ON TABLE task_backup_phase4 IS 'Backup of task table before Phase 4 cleanup. Can be dropped after successful migration verification.';

-- Validate that all tasks are properly migrated before cleanup
DO $$
DECLARE
    task_count integer;
    task_base_count integer;
    regular_count integer;
    mastery_count integer;
    validation_error text := '';
BEGIN
    -- Count tasks in original table
    SELECT COUNT(*) INTO task_count FROM task;
    SELECT COUNT(*) INTO task_base_count FROM task_base;
    SELECT COUNT(*) INTO regular_count FROM regular_tasks;
    SELECT COUNT(*) INTO mastery_count FROM mastery_tasks;
    
    RAISE NOTICE 'Phase 4 Cleanup Validation:';
    RAISE NOTICE '  Original task table: % tasks', task_count;
    RAISE NOTICE '  New task_base table: % tasks', task_base_count;
    RAISE NOTICE '  Regular tasks: %', regular_count;
    RAISE NOTICE '  Mastery tasks: %', mastery_count;
    
    -- Validate counts match
    IF task_count != task_base_count THEN
        validation_error := validation_error || format('Task count mismatch: task(%s) != task_base(%s). ', task_count, task_base_count);
    END IF;
    
    IF task_count != (regular_count + mastery_count) THEN
        validation_error := validation_error || format('Task split mismatch: task(%s) != regular(%s) + mastery(%s). ', task_count, regular_count, mastery_count);
    END IF;
    
    -- Validate that all tasks have corresponding entries in new structure
    IF EXISTS (
        SELECT 1 FROM task t
        LEFT JOIN task_base tb ON t.id = tb.id
        WHERE tb.id IS NULL
    ) THEN
        validation_error := validation_error || 'Found tasks without corresponding task_base entries. ';
    END IF;
    
    -- Check for orphaned entries in new structure
    IF EXISTS (
        SELECT 1 FROM task_base tb
        LEFT JOIN task t ON tb.id = t.id
        WHERE t.id IS NULL
    ) THEN
        validation_error := validation_error || 'Found task_base entries without corresponding task entries. ';
    END IF;
    
    -- If any validation errors, abort cleanup
    IF validation_error != '' THEN
        RAISE EXCEPTION 'CLEANUP ABORTED: %', validation_error;
    END IF;
    
    RAISE NOTICE 'SUCCESS: All validation checks passed. Proceeding with cleanup.';
END;
$$;

-- Remove old columns that are now handled by the new structure
-- These columns are now redundant:
-- - is_mastery: Determined by presence in regular_tasks vs mastery_tasks
-- - order_in_section: Moved to regular_tasks table
-- - max_attempts: Moved to regular_tasks table

ALTER TABLE task DROP COLUMN IF EXISTS is_mastery;
ALTER TABLE task DROP COLUMN IF EXISTS order_in_section; 
ALTER TABLE task DROP COLUMN IF EXISTS max_attempts;

-- Add comment explaining the new minimal task table
COMMENT ON TABLE task IS 'Legacy task table - Phase 4 cleanup completed. Most functionality moved to task_base + regular_tasks/mastery_tasks. This table may be dropped in future once all references are updated.';

-- Verify final state
DO $$
DECLARE
    task_columns text;
BEGIN
    -- Get remaining columns in task table
    SELECT string_agg(column_name, ', ' ORDER BY ordinal_position)
    INTO task_columns
    FROM information_schema.columns 
    WHERE table_name = 'task' AND table_schema = 'public';
    
    RAISE NOTICE 'Phase 4 Cleanup Complete:';
    RAISE NOTICE '  Remaining task table columns: %', task_columns;
    RAISE NOTICE '  Migration completed successfully';
    RAISE NOTICE '  Views now point to new structure (task_base + specific tables)';
    RAISE NOTICE '  Dual-write disabled via feature flag';
    RAISE NOTICE '  Backup created: task_backup_phase4';
END;
$$;