-- Schema-Fix Migration: Maps `instruction` to `title` and adds missing columns
-- Fixes blocker for Batch 3-6 migrations
-- 
-- Problem:
-- - task_base has `instruction` instead of `title`
-- - regular_tasks/mastery_tasks missing prompt, grading_criteria, difficulty_level, concept_explanation
-- 
-- Solution:
-- 1. Add missing columns to regular_tasks and mastery_tasks
-- 2. Migrate data from task_base.instruction to new prompt columns
-- 3. Add title column to task_base (copy from instruction)
-- 4. Create views with correct mapping

-- Step 1: Add missing columns to regular_tasks
ALTER TABLE regular_tasks ADD COLUMN IF NOT EXISTS prompt TEXT;
ALTER TABLE regular_tasks ADD COLUMN IF NOT EXISTS grading_criteria TEXT[];

-- Step 2: Add missing columns to mastery_tasks  
ALTER TABLE mastery_tasks ADD COLUMN IF NOT EXISTS prompt TEXT;
ALTER TABLE mastery_tasks ADD COLUMN IF NOT EXISTS difficulty_level INTEGER DEFAULT 1;
ALTER TABLE mastery_tasks ADD COLUMN IF NOT EXISTS concept_explanation TEXT;

-- Step 3: Add title column to task_base
ALTER TABLE task_base ADD COLUMN IF NOT EXISTS title TEXT;

-- Step 4: Migrate existing data
-- Copy instruction to title for compatibility
UPDATE task_base SET title = instruction WHERE title IS NULL;

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

-- Step 5: Ensure title is NOT NULL (after data migration)
ALTER TABLE task_base ALTER COLUMN title SET NOT NULL;

-- Step 6: Create/Replace views with correct schema
-- These views are required for Batch 3-6 migrations

-- Regular tasks view with all expected columns
CREATE OR REPLACE VIEW all_regular_tasks AS
SELECT 
  t.id,
  t.section_id,
  t.title,                    -- Use title instead of instruction
  t.task_type,
  t.order_in_section,
  t.created_at,
  COALESCE(r.prompt, t.instruction) as prompt,  -- Fallback to instruction
  r.max_attempts,
  r.grading_criteria,
  FALSE as is_mastery,
  t.instruction,              -- Keep instruction for compatibility
  t.criteria,
  t.assessment_criteria,
  t.solution_hints,
  t.updated_at
FROM task_base t
JOIN regular_tasks r ON r.task_id = t.id;

-- Mastery tasks view with all expected columns
CREATE OR REPLACE VIEW all_mastery_tasks AS
SELECT
  t.id,
  t.section_id,
  t.title,                    -- Use title instead of instruction
  t.task_type,
  t.order_in_section,
  t.created_at,
  COALESCE(m.prompt, t.instruction) as prompt,  -- Fallback to instruction
  m.difficulty_level,
  m.concept_explanation,
  TRUE as is_mastery,
  t.instruction,              -- Keep instruction for compatibility
  t.criteria,
  t.assessment_criteria,
  t.solution_hints,
  t.updated_at
FROM task_base t
JOIN mastery_tasks m ON m.task_id = t.id;

-- Step 7: Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_task_base_section_id ON task_base(section_id);
CREATE INDEX IF NOT EXISTS idx_task_base_order_in_section ON task_base(order_in_section);

-- Step 8: Validation
DO $$
DECLARE
    v_task_base_count INTEGER;
    v_regular_tasks_count INTEGER;
    v_mastery_tasks_count INTEGER;
    v_tasks_without_title INTEGER;
    v_regular_without_prompt INTEGER;
    v_mastery_without_prompt INTEGER;
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
    
    RAISE NOTICE 'Schema-Fix Migration Validation:';
    RAISE NOTICE '  Task Base entries: %', v_task_base_count;
    RAISE NOTICE '  Regular Tasks: %', v_regular_tasks_count;
    RAISE NOTICE '  Mastery Tasks: %', v_mastery_tasks_count;
    RAISE NOTICE '  Tasks without title: %', v_tasks_without_title;
    RAISE NOTICE '  Regular Tasks without prompt: %', v_regular_without_prompt;
    RAISE NOTICE '  Mastery Tasks without prompt: %', v_mastery_without_prompt;
    
    IF v_tasks_without_title > 0 THEN
        RAISE EXCEPTION 'MIGRATION FAILED: % tasks have no title', v_tasks_without_title;
    END IF;
    
    RAISE NOTICE 'SUCCESS: Schema-Fix Migration completed successfully.';
    RAISE NOTICE 'Batch 3-6 migrations can now be deployed.';
END;
$$;

-- Documentation comments
COMMENT ON COLUMN task_base.title IS 'Task title - added in Schema-Fix Migration. Replaces instruction in views.';
COMMENT ON COLUMN regular_tasks.prompt IS 'Task prompt - migrated from task_base.instruction';
COMMENT ON COLUMN regular_tasks.grading_criteria IS 'Grading criteria for automatic evaluation';
COMMENT ON COLUMN mastery_tasks.prompt IS 'Task prompt - migrated from task_base.instruction';
COMMENT ON COLUMN mastery_tasks.difficulty_level IS 'Difficulty level (1-5) for spaced repetition';
COMMENT ON COLUMN mastery_tasks.concept_explanation IS 'Concept explanation for students';