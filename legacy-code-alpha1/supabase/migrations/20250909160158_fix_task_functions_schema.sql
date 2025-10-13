-- Fix task creation functions to use correct column names

-- Fix create_regular_task
DROP FUNCTION IF EXISTS public.create_regular_task(TEXT, UUID, TEXT, TEXT, TEXT, INT, INT, TEXT[]);
CREATE OR REPLACE FUNCTION public.create_regular_task(
    p_session_id TEXT,
    p_section_id UUID,
    p_title TEXT,
    p_prompt TEXT,
    p_task_type TEXT,
    p_order_in_section INT DEFAULT 1,
    p_max_attempts INT DEFAULT 1,
    p_grading_criteria TEXT[] DEFAULT NULL
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
        JOIN learning_unit lu ON lu.id = s.unit_id  -- Fixed: changed from learning_unit_id
        WHERE s.id = p_section_id AND lu.creator_id = v_user_id  -- Fixed: changed from created_by
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Begin transaction
    BEGIN
        -- Step 1: Insert into task_base
        INSERT INTO task_base (section_id, title, task_type, order_in_section)
        VALUES (p_section_id, p_title, p_task_type, p_order_in_section)
        RETURNING id INTO v_task_id;

        -- Step 2: Insert into regular_tasks
        INSERT INTO regular_tasks (task_id, prompt, max_attempts, grading_criteria)
        VALUES (v_task_id, p_prompt, p_max_attempts, p_grading_criteria);

        RETURN v_task_id;
    EXCEPTION
        WHEN OTHERS THEN
            -- Rollback will happen automatically
            RAISE;
    END;
END;
$$;

GRANT EXECUTE ON FUNCTION public.create_regular_task TO anon;

-- Fix create_mastery_task
DROP FUNCTION IF EXISTS public.create_mastery_task(TEXT, UUID, TEXT, TEXT, TEXT, INT, TEXT);
CREATE OR REPLACE FUNCTION public.create_mastery_task(
    p_session_id TEXT,
    p_section_id UUID,
    p_title TEXT,
    p_prompt TEXT,
    p_task_type TEXT,
    p_difficulty_level INT DEFAULT 1,
    p_concept_explanation TEXT DEFAULT NULL
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
        JOIN learning_unit lu ON lu.id = s.unit_id  -- Fixed: changed from learning_unit_id
        WHERE s.id = p_section_id AND lu.creator_id = v_user_id  -- Fixed: changed from created_by
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Begin transaction
    BEGIN
        -- Step 1: Insert into task_base
        INSERT INTO task_base (section_id, title, task_type, order_in_section)
        VALUES (p_section_id, p_title, p_task_type, 999) -- Mastery tasks don't have order
        RETURNING id INTO v_task_id;

        -- Step 2: Insert into mastery_tasks
        INSERT INTO mastery_tasks (task_id, prompt, difficulty_level, concept_explanation)
        VALUES (v_task_id, p_prompt, p_difficulty_level, p_concept_explanation);

        RETURN v_task_id;
    EXCEPTION
        WHEN OTHERS THEN
            -- Rollback will happen automatically
            RAISE;
    END;
END;
$$;

GRANT EXECUTE ON FUNCTION public.create_mastery_task TO anon;