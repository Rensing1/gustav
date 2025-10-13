-- Fix create_regular_task and create_mastery_task to include instruction column

-- Update create_regular_task to include instruction
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
        JOIN learning_unit lu ON lu.id = s.unit_id
        WHERE s.id = p_section_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Begin transaction
    BEGIN
        -- Step 1: Insert into task_base with instruction
        INSERT INTO task_base (section_id, title, instruction, task_type, order_in_section)
        VALUES (p_section_id, p_title, p_prompt, p_task_type, p_order_in_section)  -- Use p_prompt for instruction
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

-- Update create_mastery_task to include instruction
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
        JOIN learning_unit lu ON lu.id = s.unit_id
        WHERE s.id = p_section_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Begin transaction
    BEGIN
        -- Step 1: Insert into task_base with instruction
        INSERT INTO task_base (section_id, title, instruction, task_type, order_in_section)
        VALUES (p_section_id, p_title, p_prompt, 'mastery', 1)  -- Use p_prompt for instruction
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

-- Also fix create_task_in_new_structure if it exists
-- Check if function exists first
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_proc 
        WHERE proname = 'create_task_in_new_structure' 
        AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
    ) THEN
        EXECUTE '
            CREATE OR REPLACE FUNCTION public.create_task_in_new_structure(
                p_session_id TEXT,
                p_section_id UUID,
                p_title TEXT,
                p_prompt TEXT,
                p_task_type TEXT DEFAULT ''regular'',
                p_max_attempts INT DEFAULT NULL,
                p_grading_criteria TEXT[] DEFAULT NULL,
                p_difficulty_level INT DEFAULT NULL,
                p_concept_explanation TEXT DEFAULT NULL
            )
            RETURNS UUID
            SECURITY DEFINER
            SET search_path = public
            LANGUAGE plpgsql AS $func$
            DECLARE
                v_user_id UUID;
                v_user_role TEXT;
                v_is_valid BOOLEAN;
                v_task_id UUID;
                v_order_in_section INT;
            BEGIN
                -- Session validation
                SELECT user_id, user_role, is_valid
                INTO v_user_id, v_user_role, v_is_valid
                FROM public.validate_session_and_get_user(p_session_id);

                IF NOT v_is_valid OR v_user_role != ''teacher'' THEN
                    RAISE EXCEPTION ''Unauthorized: Only teachers can create tasks'';
                END IF;

                -- Check ownership through section
                IF NOT EXISTS (
                    SELECT 1 
                    FROM unit_section s
                    JOIN learning_unit lu ON lu.id = s.unit_id
                    WHERE s.id = p_section_id AND lu.created_by = v_user_id
                ) THEN
                    RAISE EXCEPTION ''Unauthorized: Teacher does not own the learning unit'';
                END IF;

                -- Get next order position
                SELECT COALESCE(MAX(order_in_section), 0) + 1
                INTO v_order_in_section
                FROM task_base
                WHERE section_id = p_section_id;

                -- Create task based on type
                IF p_task_type = ''mastery'' THEN
                    -- Insert into task_base with instruction
                    INSERT INTO task_base (section_id, title, instruction, task_type, order_in_section)
                    VALUES (p_section_id, p_title, p_prompt, p_task_type, v_order_in_section)
                    RETURNING id INTO v_task_id;

                    -- Insert into mastery_task
                    INSERT INTO mastery_task (task_id, difficulty_level, concept_explanation)
                    VALUES (v_task_id, COALESCE(p_difficulty_level, 1), p_concept_explanation);
                ELSE
                    -- Insert into task_base with instruction
                    INSERT INTO task_base (section_id, title, instruction, prompt, task_type, order_in_section)
                    VALUES (p_section_id, p_title, p_prompt, p_prompt, p_task_type, v_order_in_section)
                    RETURNING id INTO v_task_id;

                    -- Insert into regular_task
                    INSERT INTO regular_task (task_id, max_attempts, grading_criteria)
                    VALUES (v_task_id, COALESCE(p_max_attempts, 1), p_grading_criteria);
                END IF;

                RETURN v_task_id;
            END;
            $func$
        ';
    END IF;
END $$;