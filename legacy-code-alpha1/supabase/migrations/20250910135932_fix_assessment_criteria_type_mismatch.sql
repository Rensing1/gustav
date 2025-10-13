-- Fix type mismatch between task_base.assessment_criteria (JSONB) and regular_tasks.grading_criteria (TEXT[])

-- Update create_regular_task to handle JSONB to TEXT[] conversion
CREATE OR REPLACE FUNCTION public.create_regular_task(
    p_session_id TEXT,
    p_section_id UUID,
    p_instruction TEXT,
    p_task_type TEXT,
    p_order_in_section INT DEFAULT 1,
    p_max_attempts INT DEFAULT 1,
    p_assessment_criteria JSONB DEFAULT NULL
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
    v_grading_criteria TEXT[];
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

    -- Convert JSONB array to TEXT[] for backward compatibility
    IF p_assessment_criteria IS NOT NULL AND jsonb_typeof(p_assessment_criteria) = 'array' THEN
        v_grading_criteria := ARRAY(SELECT jsonb_array_elements_text(p_assessment_criteria));
    ELSE
        v_grading_criteria := NULL;
    END IF;

    -- Begin transaction
    BEGIN
        -- Step 1: Insert into task_base with instruction
        INSERT INTO task_base (section_id, instruction, task_type, order_in_section, assessment_criteria)
        VALUES (p_section_id, p_instruction, p_task_type, p_order_in_section, p_assessment_criteria)
        RETURNING id INTO v_task_id;

        -- Step 2: Insert into regular_tasks with converted grading_criteria
        INSERT INTO regular_tasks (task_id, prompt, max_attempts, grading_criteria)
        VALUES (v_task_id, p_instruction, p_max_attempts, v_grading_criteria);

        RETURN v_task_id;
    EXCEPTION
        WHEN OTHERS THEN
            -- Rollback will happen automatically
            RAISE;
    END;
END;
$$;

-- Update create_mastery_task similarly
CREATE OR REPLACE FUNCTION public.create_mastery_task(
    p_session_id TEXT,
    p_section_id UUID,
    p_instruction TEXT,
    p_task_type TEXT,
    p_order_in_section INT DEFAULT 1,
    p_difficulty_level INT DEFAULT 1,
    p_assessment_criteria JSONB DEFAULT NULL
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

        -- Step 2: Insert into mastery_tasks (no grading_criteria needed for mastery tasks)
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