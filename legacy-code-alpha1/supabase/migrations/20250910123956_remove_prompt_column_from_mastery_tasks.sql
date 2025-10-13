-- Remove redundant 'prompt' column from mastery_tasks
-- The 'instruction' column from task_base should be used instead
-- This simplifies the schema and removes confusion

-- First update the create_mastery_task function to not use prompt
DROP FUNCTION IF EXISTS public.create_mastery_task(TEXT, UUID, TEXT, TEXT, TEXT, JSONB, TEXT, INTEGER, TEXT);

CREATE OR REPLACE FUNCTION public.create_mastery_task(
    p_session_id TEXT,
    p_section_id UUID,
    p_title TEXT,
    p_instruction TEXT,
    p_task_type TEXT,
    p_assessment_criteria JSONB,
    p_solution_hints TEXT,
    p_difficulty_level INTEGER DEFAULT 1
)
RETURNS UUID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_task_id UUID;
    v_next_order INTEGER;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized';
    END IF;

    -- Check if teacher owns the unit
    IF NOT EXISTS (
        SELECT 1 
        FROM unit_section s
        JOIN learning_unit u ON u.id = s.unit_id
        WHERE s.id = p_section_id AND u.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized - not owner of unit';
    END IF;

    -- Get next order
    SELECT COALESCE(MAX(order_in_section), 0) + 1
    INTO v_next_order
    FROM task_base
    WHERE section_id = p_section_id;

    -- Create task in task_base
    INSERT INTO task_base (
        section_id,
        title,
        instruction,
        task_type,
        assessment_criteria,
        solution_hints,
        order_in_section
    ) VALUES (
        p_section_id,
        p_title,
        p_instruction,
        p_task_type,
        p_assessment_criteria,
        p_solution_hints,
        v_next_order
    ) RETURNING id INTO v_task_id;

    -- Create mastery task entry without prompt
    INSERT INTO mastery_tasks (
        task_id,
        difficulty_level,
        spaced_repetition_interval
    ) VALUES (
        v_task_id,
        p_difficulty_level,
        1  -- Default interval
    );

    RETURN v_task_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.create_mastery_task(TEXT, UUID, TEXT, TEXT, TEXT, JSONB, TEXT, INTEGER) TO anon;

-- Drop view that depends on prompt column
DROP VIEW IF EXISTS all_mastery_tasks CASCADE;

-- Drop the prompt column
ALTER TABLE mastery_tasks DROP COLUMN IF EXISTS prompt;

-- Recreate the view without prompt
CREATE VIEW all_mastery_tasks AS
SELECT 
    t.*,
    mt.difficulty_level,
    mt.spaced_repetition_interval
FROM task_base t
JOIN mastery_tasks mt ON t.id = mt.task_id;

GRANT SELECT ON all_mastery_tasks TO authenticated;

-- Update comments
COMMENT ON TABLE mastery_tasks IS 'Mastery task specific attributes. Use instruction from task_base for the task prompt.';
COMMENT ON FUNCTION public.create_mastery_task(TEXT, UUID, TEXT, TEXT, TEXT, JSONB, TEXT, INTEGER) IS 'Creates mastery task. Uses instruction from task_base, prompt column removed.';