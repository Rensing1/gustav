-- Fix column reference error in update_task_in_new_structure
-- The function references s.learning_unit_id but the column is s.unit_id

CREATE OR REPLACE FUNCTION public.update_task_in_new_structure(
    p_session_id TEXT,
    p_task_id UUID,
    p_title TEXT,
    p_prompt TEXT,
    p_task_type TEXT,
    p_order_in_section INT DEFAULT NULL,
    p_max_attempts INT DEFAULT NULL,
    p_grading_criteria TEXT[] DEFAULT NULL,
    p_difficulty_level INT DEFAULT NULL,
    p_concept_explanation TEXT DEFAULT NULL
)
RETURNS VOID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_is_regular BOOLEAN;
    v_is_mastery BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can update tasks';
    END IF;

    -- Check if teacher has access to the task
    -- FIXED: Changed s.learning_unit_id to s.unit_id
    IF NOT EXISTS (
        SELECT 1 
        FROM task_base t
        JOIN unit_section s ON s.id = t.section_id
        JOIN learning_unit lu ON lu.id = s.unit_id  -- Fixed: was s.learning_unit_id
        WHERE t.id = p_task_id AND lu.created_by = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Detect task type
    SELECT EXISTS(SELECT 1 FROM regular_tasks WHERE task_id = p_task_id) INTO v_is_regular;
    SELECT EXISTS(SELECT 1 FROM mastery_tasks WHERE task_id = p_task_id) INTO v_is_mastery;

    IF NOT v_is_regular AND NOT v_is_mastery THEN
        RAISE EXCEPTION 'Task not found in either regular_tasks or mastery_tasks';
    END IF;

    -- Update task_base
    UPDATE task_base
    SET 
        title = p_title,
        task_type = p_task_type,
        order_in_section = CASE 
            WHEN v_is_regular THEN COALESCE(p_order_in_section, order_in_section)
            ELSE order_in_section -- Mastery tasks don't have order
        END
    WHERE id = p_task_id;

    -- Update type-specific table
    IF v_is_regular THEN
        UPDATE regular_tasks
        SET 
            prompt = p_prompt,
            max_attempts = COALESCE(p_max_attempts, max_attempts),
            grading_criteria = COALESCE(p_grading_criteria, grading_criteria)
        WHERE task_id = p_task_id;
    ELSE
        UPDATE mastery_tasks
        SET 
            prompt = p_prompt,
            difficulty_level = COALESCE(p_difficulty_level, difficulty_level),
            concept_explanation = COALESCE(p_concept_explanation, concept_explanation)
        WHERE task_id = p_task_id;
    END IF;
END;
$$;

-- Ensure permissions remain the same
GRANT EXECUTE ON FUNCTION public.update_task_in_new_structure TO anon;