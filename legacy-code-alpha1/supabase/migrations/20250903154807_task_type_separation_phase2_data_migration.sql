-- Phase 2: Task Type Separation - Data Migration
-- Migrates all existing tasks from 'task' table to new structure (task_base + specific tables)

-- Function to migrate existing tasks to new structure
CREATE OR REPLACE FUNCTION migrate_tasks_to_new_structure()
RETURNS TABLE (
    migrated_count integer,
    regular_count integer,
    mastery_count integer,
    error_count integer
) AS $$
DECLARE
    task_record RECORD;
    migrated_count integer := 0;
    regular_count integer := 0;
    mastery_count integer := 0;
    error_count integer := 0;
    new_task_id uuid;
BEGIN
    -- Loop through all existing tasks
    FOR task_record IN 
        SELECT id, section_id, instruction, task_type, order_in_section, 
               criteria, assessment_criteria, solution_hints, is_mastery, max_attempts,
               created_at, updated_at
        FROM task
        ORDER BY created_at
    LOOP
        BEGIN
            -- Insert into task_base (shared attributes)
            INSERT INTO task_base (
                id, section_id, instruction, task_type, criteria, 
                assessment_criteria, solution_hints, created_at, updated_at
            ) VALUES (
                task_record.id,
                task_record.section_id,
                task_record.instruction,
                task_record.task_type,
                task_record.criteria,
                COALESCE(task_record.assessment_criteria, '[]'::jsonb),
                task_record.solution_hints,
                task_record.created_at,
                task_record.updated_at
            );

            -- Insert into specific table based on is_mastery flag
            IF COALESCE(task_record.is_mastery, false) = true THEN
                -- Mastery task
                INSERT INTO mastery_tasks (task_id)
                VALUES (task_record.id);
                mastery_count := mastery_count + 1;
            ELSE
                -- Regular task
                INSERT INTO regular_tasks (task_id, order_in_section, max_attempts)
                VALUES (
                    task_record.id,
                    COALESCE(task_record.order_in_section, 1),
                    COALESCE(task_record.max_attempts, 1)
                );
                regular_count := regular_count + 1;
            END IF;

            migrated_count := migrated_count + 1;
            
        EXCEPTION
            WHEN OTHERS THEN
                -- Log error and continue with next task
                RAISE WARNING 'Failed to migrate task %: %', task_record.id, SQLERRM;
                error_count := error_count + 1;
        END;
    END LOOP;

    RETURN QUERY SELECT migrated_count, regular_count, mastery_count, error_count;
END;
$$ LANGUAGE plpgsql;

-- Run the migration function
DO $$
DECLARE
    result RECORD;
BEGIN
    -- Run migration
    SELECT * FROM migrate_tasks_to_new_structure() INTO result;
    
    RAISE NOTICE 'Task migration completed:';
    RAISE NOTICE '  Total migrated: %', result.migrated_count;
    RAISE NOTICE '  Regular tasks: %', result.regular_count;
    RAISE NOTICE '  Mastery tasks: %', result.mastery_count;
    RAISE NOTICE '  Errors: %', result.error_count;
    
    -- Verify migration by comparing counts
    IF (SELECT COUNT(*) FROM task) = result.migrated_count THEN
        RAISE NOTICE 'SUCCESS: All tasks successfully migrated to new structure';
    ELSE
        RAISE EXCEPTION 'MIGRATION FAILED: Count mismatch between old and new structure';
    END IF;
END;
$$;

-- Drop the migration function (no longer needed)
DROP FUNCTION migrate_tasks_to_new_structure();

-- Add comments documenting the migration
COMMENT ON TABLE task_base IS 'Base table for all tasks - Phase 2 of Task Type Separation. Contains shared attributes. Migrated from task table on 2025-09-03.';
COMMENT ON TABLE regular_tasks IS 'Regular tasks with order and attempt limits - Phase 2 of Task Type Separation. Migrated from task table on 2025-09-03.';
COMMENT ON TABLE mastery_tasks IS 'Mastery tasks (Wissensfestiger) for spaced repetition - Phase 2 of Task Type Separation. Migrated from task table on 2025-09-03.';