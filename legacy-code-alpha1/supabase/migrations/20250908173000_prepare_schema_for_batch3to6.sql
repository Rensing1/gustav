-- Prepare Schema for Batch 3-6 Migrations
-- This migration fixes schema mismatches to unblock Batch 3-6 functions
-- 
-- Key Issues Fixed:
-- 1. task_base missing 'title' column (has 'instruction' instead)
-- 2. task_base missing 'order_in_section' (it's in regular_tasks)
-- 3. regular_tasks/mastery_tasks missing prompt, grading_criteria, etc.
-- 4. Views expecting different schema than what exists

-- Step 1: Add missing columns to task_base
ALTER TABLE task_base ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE task_base ADD COLUMN IF NOT EXISTS order_in_section INTEGER DEFAULT 1;

-- Step 2: Add missing columns to regular_tasks
ALTER TABLE regular_tasks ADD COLUMN IF NOT EXISTS prompt TEXT;
ALTER TABLE regular_tasks ADD COLUMN IF NOT EXISTS grading_criteria TEXT[];

-- Step 3: Add missing columns to mastery_tasks  
ALTER TABLE mastery_tasks ADD COLUMN IF NOT EXISTS prompt TEXT;
ALTER TABLE mastery_tasks ADD COLUMN IF NOT EXISTS difficulty_level INTEGER DEFAULT 1;
ALTER TABLE mastery_tasks ADD COLUMN IF NOT EXISTS concept_explanation TEXT;

-- Step 4: Migrate existing data
-- Copy instruction to title for compatibility
UPDATE task_base SET title = instruction WHERE title IS NULL;

-- Copy order_in_section from regular_tasks to task_base
UPDATE task_base t
SET order_in_section = r.order_in_section
FROM regular_tasks r
WHERE t.id = r.task_id AND t.order_in_section = 1 AND r.order_in_section != 1;

-- For mastery tasks, set order_in_section to 999 (they don't have order)
UPDATE task_base t
SET order_in_section = 999
FROM mastery_tasks m
WHERE t.id = m.task_id;

-- Copy instruction to prompt in regular_tasks
UPDATE regular_tasks r
SET prompt = t.instruction
FROM task_base t
WHERE r.task_id = t.id AND r.prompt IS NULL;

-- Copy instruction to prompt in mastery_tasks
UPDATE mastery_tasks m
SET prompt = t.instruction
FROM task_base t
WHERE m.task_id = t.id AND m.prompt IS NULL;

-- Step 5: Ensure columns are NOT NULL where required
ALTER TABLE task_base ALTER COLUMN title SET NOT NULL;

-- Step 6: Drop and recreate views if they exist (to avoid conflicts)
DROP VIEW IF EXISTS all_regular_tasks CASCADE;
DROP VIEW IF EXISTS all_mastery_tasks CASCADE;

-- Note: The actual views will be created by Batch 3 migration
-- We're just ensuring the schema is ready for them

-- Step 7: Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_task_base_section_id ON task_base(section_id);
CREATE INDEX IF NOT EXISTS idx_task_base_order_in_section ON task_base(order_in_section);
CREATE INDEX IF NOT EXISTS idx_regular_tasks_order ON regular_tasks(order_in_section);

-- Step 8: Validation
DO $$
DECLARE
    v_task_base_count INTEGER;
    v_regular_tasks_count INTEGER;
    v_mastery_tasks_count INTEGER;
    v_tasks_without_title INTEGER;
    v_regular_without_prompt INTEGER;
    v_mastery_without_prompt INTEGER;
    v_order_mismatch INTEGER;
BEGIN
    -- Count entries
    SELECT COUNT(*) INTO v_task_base_count FROM task_base;
    SELECT COUNT(*) INTO v_regular_tasks_count FROM regular_tasks;
    SELECT COUNT(*) INTO v_mastery_tasks_count FROM mastery_tasks;
    
    -- Check for missing data
    SELECT COUNT(*) INTO v_tasks_without_title 
    FROM task_base WHERE title IS NULL;
    
    SELECT COUNT(*) INTO v_regular_without_prompt
    FROM regular_tasks WHERE prompt IS NULL;
    
    SELECT COUNT(*) INTO v_mastery_without_prompt
    FROM mastery_tasks WHERE prompt IS NULL;
    
    -- Check order_in_section synchronization
    SELECT COUNT(*) INTO v_order_mismatch
    FROM task_base t
    JOIN regular_tasks r ON t.id = r.task_id
    WHERE t.order_in_section != r.order_in_section;
    
    RAISE NOTICE 'Schema Preparation Validation:';
    RAISE NOTICE '  Task Base entries: %', v_task_base_count;
    RAISE NOTICE '  Regular Tasks: %', v_regular_tasks_count;
    RAISE NOTICE '  Mastery Tasks: %', v_mastery_tasks_count;
    RAISE NOTICE '  Tasks without title: %', v_tasks_without_title;
    RAISE NOTICE '  Regular Tasks without prompt: %', v_regular_without_prompt;
    RAISE NOTICE '  Mastery Tasks without prompt: %', v_mastery_without_prompt;
    RAISE NOTICE '  Order mismatches: %', v_order_mismatch;
    
    IF v_tasks_without_title > 0 THEN
        RAISE EXCEPTION 'MIGRATION FAILED: % tasks have no title', v_tasks_without_title;
    END IF;
    
    RAISE NOTICE 'SUCCESS: Schema prepared for Batch 3-6 migrations.';
END;
$$;

-- Documentation comments
COMMENT ON COLUMN task_base.title IS 'Task title - copied from instruction for Batch 3-6 compatibility';
COMMENT ON COLUMN task_base.order_in_section IS 'Order within section - synchronized with regular_tasks';
COMMENT ON COLUMN regular_tasks.prompt IS 'Task prompt - migrated from task_base.instruction';
COMMENT ON COLUMN regular_tasks.grading_criteria IS 'Grading criteria for automatic evaluation';
COMMENT ON COLUMN mastery_tasks.prompt IS 'Task prompt - migrated from task_base.instruction';
COMMENT ON COLUMN mastery_tasks.difficulty_level IS 'Difficulty level (1-5) for spaced repetition';
COMMENT ON COLUMN mastery_tasks.concept_explanation IS 'Concept explanation for students';