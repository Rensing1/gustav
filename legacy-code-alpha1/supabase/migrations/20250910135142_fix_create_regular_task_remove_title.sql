-- Fix create_regular_task and create_mastery_task functions to use consistent parameter names
-- Tasks only have instruction, assessment_criteria and solution_hints

-- Update create_regular_task with consistent naming
CREATE OR REPLACE FUNCTION public.create_regular_task(
    p_session_id TEXT,
    p_section_id UUID,
    p_instruction TEXT,  -- Use instruction consistently
    p_task_type TEXT,
    p_order_in_section INT DEFAULT 1,
    p_max_attempts INT DEFAULT 1,
    p_assessment_criteria JSONB DEFAULT NULL  -- Use assessment_criteria consistently
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
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can create tasks';
    END IF;

    -- Check if teacher has access to the section
    IF NOT EXISTS (
        SELECT 1 
        FROM unit_section s
        JOIN learning_unit lu ON lu.id = s.unit_id
        WHERE s.id = p_section_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Begin transaction
    BEGIN
        -- Step 1: Insert into task_base with instruction
        INSERT INTO task_base (section_id, instruction, task_type, order_in_section, assessment_criteria)
        VALUES (p_section_id, p_instruction, p_task_type, p_order_in_section, p_assessment_criteria)
        RETURNING id INTO v_task_id;

        -- Step 2: Insert into regular_tasks (prompt is stored for backward compatibility)
        INSERT INTO regular_tasks (task_id, prompt, max_attempts, grading_criteria)
        VALUES (v_task_id, p_instruction, p_max_attempts, p_assessment_criteria);

        RETURN v_task_id;
    EXCEPTION
        WHEN OTHERS THEN
            -- Rollback will happen automatically
            RAISE;
    END;
END;
$$;

-- Update create_mastery_task with consistent naming
CREATE OR REPLACE FUNCTION public.create_mastery_task(
    p_session_id TEXT,
    p_section_id UUID,
    p_instruction TEXT,  -- Use instruction consistently
    p_task_type TEXT,
    p_order_in_section INT DEFAULT 1,
    p_difficulty_level INT DEFAULT 1,
    p_assessment_criteria TEXT[] DEFAULT NULL  -- Add assessment_criteria for consistency
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
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can create tasks';
    END IF;

    -- Check if teacher has access to the section
    IF NOT EXISTS (
        SELECT 1 
        FROM unit_section s
        JOIN learning_unit lu ON lu.id = s.unit_id
        WHERE s.id = p_section_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Begin transaction
    BEGIN
        -- Step 1: Insert into task_base with instruction
        INSERT INTO task_base (section_id, instruction, task_type, order_in_section, assessment_criteria)
        VALUES (p_section_id, p_instruction, p_task_type, p_order_in_section, p_assessment_criteria)
        RETURNING id INTO v_task_id;

        -- Step 2: Insert into mastery_tasks (prompt is stored for backward compatibility)
        INSERT INTO mastery_tasks (task_id, prompt, difficulty_level, concept_explanation)
        VALUES (v_task_id, p_instruction, p_difficulty_level, NULL);

        RETURN v_task_id;
    EXCEPTION
        WHEN OTHERS THEN
            -- Rollback will happen automatically
            RAISE;
    END;
END;
$$;