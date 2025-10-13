-- Fix create_mastery_task to include all task_base fields
-- Mastery tasks need instruction, assessment_criteria and solution_hints just like regular tasks

DROP FUNCTION IF EXISTS public.create_mastery_task(TEXT, UUID, TEXT, TEXT, TEXT, INT, TEXT);
CREATE OR REPLACE FUNCTION public.create_mastery_task(
    p_session_id TEXT,
    p_section_id UUID,
    p_title TEXT,
    p_instruction TEXT,  -- Added: important for mastery tasks
    p_task_type TEXT,
    p_assessment_criteria JSONB DEFAULT NULL,  -- Added: evaluation criteria
    p_solution_hints TEXT DEFAULT NULL,  -- Added: hints for students
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
        -- Step 1: Insert into task_base with ALL fields
        INSERT INTO task_base (
            section_id, 
            title, 
            instruction,  -- Now included
            task_type, 
            assessment_criteria,  -- Now included
            solution_hints,  -- Now included
            order_in_section
        )
        VALUES (
            p_section_id, 
            p_title, 
            p_instruction,
            p_task_type,
            p_assessment_criteria,
            p_solution_hints,
            999  -- Mastery tasks get high order number
        )
        RETURNING id INTO v_task_id;

        -- Step 2: Insert into mastery_tasks with mastery-specific fields
        INSERT INTO mastery_tasks (
            task_id, 
            prompt,  -- Can override instruction if needed
            difficulty_level, 
            concept_explanation
        )
        VALUES (
            v_task_id, 
            p_instruction,  -- Use instruction as prompt by default
            p_difficulty_level, 
            p_concept_explanation
        );

        RETURN v_task_id;
    EXCEPTION
        WHEN OTHERS THEN
            -- Rollback will happen automatically
            RAISE;
    END;
END;
$$;

GRANT EXECUTE ON FUNCTION public.create_mastery_task TO anon;

-- Also update the Python function calls to match
-- The Python functions in db_queries.py and db/content/tasks.py need to be aligned