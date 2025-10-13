-- Batch 3: Task CRUD Operations
-- 10 Functions for Task Creation, Update, Delete and Reading
-- Requires views: all_regular_tasks, all_mastery_tasks

-- First, ensure the views exist
CREATE OR REPLACE VIEW all_regular_tasks AS
SELECT 
  t.id,
  t.section_id,
  t.title,
  t.task_type,
  t.order_in_section,
  t.created_at,
  r.prompt,
  r.max_attempts,
  r.grading_criteria,
  FALSE as is_mastery
FROM task_base t
JOIN regular_tasks r ON r.task_id = t.id;

CREATE OR REPLACE VIEW all_mastery_tasks AS
SELECT
  t.id,
  t.section_id,
  t.title,
  t.task_type,
  t.order_in_section,
  t.created_at,
  m.prompt,
  m.difficulty_level,
  m.concept_explanation,
  TRUE as is_mastery
FROM task_base t
JOIN mastery_tasks m ON m.task_id = t.id;

-- 1. create_regular_task - Creates a regular task with two-step insert
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
        JOIN learning_unit lu ON lu.id = s.learning_unit_id
        WHERE s.id = p_section_id AND lu.created_by = v_user_id
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

-- 2. create_mastery_task - Creates a mastery task with two-step insert
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
        JOIN learning_unit lu ON lu.id = s.learning_unit_id
        WHERE s.id = p_section_id AND lu.created_by = v_user_id
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

-- 3. create_task_in_new_structure - Router function that delegates based on is_mastery
CREATE OR REPLACE FUNCTION public.create_task_in_new_structure(
    p_session_id TEXT,
    p_section_id UUID,
    p_title TEXT,
    p_prompt TEXT,
    p_task_type TEXT,
    p_is_mastery BOOLEAN,
    p_order_in_section INT DEFAULT 1,
    p_max_attempts INT DEFAULT 1,
    p_grading_criteria TEXT[] DEFAULT NULL,
    p_difficulty_level INT DEFAULT 1,
    p_concept_explanation TEXT DEFAULT NULL
)
RETURNS UUID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_task_id UUID;
BEGIN
    IF p_is_mastery THEN
        -- Create mastery task
        v_task_id := public.create_mastery_task(
            p_session_id,
            p_section_id,
            p_title,
            p_prompt,
            p_task_type,
            p_difficulty_level,
            p_concept_explanation
        );
    ELSE
        -- Create regular task
        v_task_id := public.create_regular_task(
            p_session_id,
            p_section_id,
            p_title,
            p_prompt,
            p_task_type,
            p_order_in_section,
            p_max_attempts,
            p_grading_criteria
        );
    END IF;

    RETURN v_task_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.create_task_in_new_structure TO anon;

-- 4. update_task_in_new_structure - Updates task with complex type detection
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
    IF NOT EXISTS (
        SELECT 1 
        FROM task_base t
        JOIN unit_section s ON s.id = t.section_id
        JOIN learning_unit lu ON lu.id = s.learning_unit_id
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

GRANT EXECUTE ON FUNCTION public.update_task_in_new_structure TO anon;

-- 5. delete_task_in_new_structure - Deletes task (CASCADE handles cleanup)
CREATE OR REPLACE FUNCTION public.delete_task_in_new_structure(
    p_session_id TEXT,
    p_task_id UUID
)
RETURNS VOID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can delete tasks';
    END IF;

    -- Check if teacher has access to the task
    IF NOT EXISTS (
        SELECT 1 
        FROM task_base t
        JOIN unit_section s ON s.id = t.section_id
        JOIN learning_unit lu ON lu.id = s.learning_unit_id
        WHERE t.id = p_task_id AND lu.created_by = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Delete from task_base (CASCADE will handle regular_tasks/mastery_tasks)
    DELETE FROM task_base WHERE id = p_task_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.delete_task_in_new_structure TO anon;

-- 6. get_tasks_for_section - Returns all tasks (regular and mastery) for a section
CREATE OR REPLACE FUNCTION public.get_tasks_for_section(
    p_session_id TEXT,
    p_section_id UUID
)
RETURNS TABLE (
    id UUID,
    section_id UUID,
    title TEXT,
    task_type TEXT,
    order_in_section INT,
    created_at TIMESTAMPTZ,
    prompt TEXT,
    is_mastery BOOLEAN,
    max_attempts INT,
    grading_criteria TEXT[],
    difficulty_level INT,
    concept_explanation TEXT
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Return combined results from both views
    RETURN QUERY
    SELECT 
        t.id,
        t.section_id,
        t.title,
        t.task_type,
        t.order_in_section,
        t.created_at,
        t.prompt,
        t.is_mastery,
        t.max_attempts,
        t.grading_criteria,
        NULL::INT as difficulty_level,
        NULL::TEXT as concept_explanation
    FROM all_regular_tasks t
    WHERE t.section_id = p_section_id
    UNION ALL
    SELECT 
        t.id,
        t.section_id,
        t.title,
        t.task_type,
        t.order_in_section,
        t.created_at,
        t.prompt,
        t.is_mastery,
        NULL::INT as max_attempts,
        NULL::TEXT[] as grading_criteria,
        t.difficulty_level,
        t.concept_explanation
    FROM all_mastery_tasks t
    WHERE t.section_id = p_section_id
    ORDER BY is_mastery, order_in_section;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_tasks_for_section TO anon;

-- 7. get_regular_tasks_for_section - Returns only regular tasks for a section
CREATE OR REPLACE FUNCTION public.get_regular_tasks_for_section(
    p_session_id TEXT,
    p_section_id UUID
)
RETURNS TABLE (
    id UUID,
    section_id UUID,
    title TEXT,
    task_type TEXT,
    order_in_section INT,
    created_at TIMESTAMPTZ,
    prompt TEXT,
    max_attempts INT,
    grading_criteria TEXT[]
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Return regular tasks
    RETURN QUERY
    SELECT 
        t.id,
        t.section_id,
        t.title,
        t.task_type,
        t.order_in_section,
        t.created_at,
        t.prompt,
        t.max_attempts,
        t.grading_criteria
    FROM all_regular_tasks t
    WHERE t.section_id = p_section_id
    ORDER BY t.order_in_section;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_regular_tasks_for_section TO anon;

-- 8. get_mastery_tasks_for_section - Returns only mastery tasks for a section
CREATE OR REPLACE FUNCTION public.get_mastery_tasks_for_section(
    p_session_id TEXT,
    p_section_id UUID
)
RETURNS TABLE (
    id UUID,
    section_id UUID,
    title TEXT,
    task_type TEXT,
    order_in_section INT,
    created_at TIMESTAMPTZ,
    prompt TEXT,
    difficulty_level INT,
    concept_explanation TEXT
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Return mastery tasks
    RETURN QUERY
    SELECT 
        t.id,
        t.section_id,
        t.title,
        t.task_type,
        t.order_in_section,
        t.created_at,
        t.prompt,
        t.difficulty_level,
        t.concept_explanation
    FROM all_mastery_tasks t
    WHERE t.section_id = p_section_id
    ORDER BY t.created_at;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_mastery_tasks_for_section TO anon;

-- 9. move_task_up - Swaps order with previous task
CREATE OR REPLACE FUNCTION public.move_task_up(
    p_session_id TEXT,
    p_task_id UUID
)
RETURNS VOID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_current_order INT;
    v_section_id UUID;
    v_prev_task_id UUID;
    v_prev_order INT;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can reorder tasks';
    END IF;

    -- Get current task info
    SELECT t.order_in_section, t.section_id
    INTO v_current_order, v_section_id
    FROM all_regular_tasks t
    WHERE t.id = p_task_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Task not found or is not a regular task';
    END IF;

    -- Check if teacher has access
    IF NOT EXISTS (
        SELECT 1 
        FROM unit_section s
        JOIN learning_unit lu ON lu.id = s.learning_unit_id
        WHERE s.id = v_section_id AND lu.created_by = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Find previous task
    SELECT t.id, t.order_in_section
    INTO v_prev_task_id, v_prev_order
    FROM all_regular_tasks t
    WHERE t.section_id = v_section_id
    AND t.order_in_section < v_current_order
    ORDER BY t.order_in_section DESC
    LIMIT 1;

    IF NOT FOUND THEN
        -- Already at the top
        RETURN;
    END IF;

    -- Swap orders
    UPDATE task_base SET order_in_section = v_current_order WHERE id = v_prev_task_id;
    UPDATE task_base SET order_in_section = v_prev_order WHERE id = p_task_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.move_task_up TO anon;

-- 10. move_task_down - Swaps order with next task
CREATE OR REPLACE FUNCTION public.move_task_down(
    p_session_id TEXT,
    p_task_id UUID
)
RETURNS VOID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_current_order INT;
    v_section_id UUID;
    v_next_task_id UUID;
    v_next_order INT;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can reorder tasks';
    END IF;

    -- Get current task info
    SELECT t.order_in_section, t.section_id
    INTO v_current_order, v_section_id
    FROM all_regular_tasks t
    WHERE t.id = p_task_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Task not found or is not a regular task';
    END IF;

    -- Check if teacher has access
    IF NOT EXISTS (
        SELECT 1 
        FROM unit_section s
        JOIN learning_unit lu ON lu.id = s.learning_unit_id
        WHERE s.id = v_section_id AND lu.created_by = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Find next task
    SELECT t.id, t.order_in_section
    INTO v_next_task_id, v_next_order
    FROM all_regular_tasks t
    WHERE t.section_id = v_section_id
    AND t.order_in_section > v_current_order
    ORDER BY t.order_in_section ASC
    LIMIT 1;

    IF NOT FOUND THEN
        -- Already at the bottom
        RETURN;
    END IF;

    -- Swap orders
    UPDATE task_base SET order_in_section = v_current_order WHERE id = v_next_task_id;
    UPDATE task_base SET order_in_section = v_next_order WHERE id = p_task_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.move_task_down TO anon;