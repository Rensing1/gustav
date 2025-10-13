-- CRITICAL FIX: The Python code calls create_submission with p_submission_text parameter
-- but the function with that signature still has old schema references
-- We need to fix the create_submission(TEXT, UUID, TEXT) function that Python actually calls

CREATE OR REPLACE FUNCTION public.create_submission(
    p_session_id TEXT,
    p_task_id UUID,
    p_submission_text TEXT  -- Keep TEXT parameter for Python compatibility
)
RETURNS UUID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_submission_id UUID;
    v_section_id UUID;
    v_course_id UUID;
    v_max_attempts INT;
    v_current_attempts INT;
    v_submission_data JSONB;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'student' THEN
        RAISE EXCEPTION 'Unauthorized: Only students can submit';
    END IF;

    -- Get task info and check if it exists
    SELECT t.section_id 
    INTO v_section_id
    FROM task_base t
    WHERE t.id = p_task_id;

    IF v_section_id IS NULL THEN
        RAISE EXCEPTION 'Task not found';
    END IF;

    -- FIXED: Get course_id for this task - correct all schema references
    SELECT cua.course_id
    INTO v_course_id
    FROM unit_section s
    JOIN learning_unit lu ON lu.id = s.unit_id  -- FIXED: was s.learning_unit_id
    JOIN course_learning_unit_assignment cua ON cua.unit_id = lu.id  -- FIXED: was cua.learning_unit_id
    WHERE s.id = v_section_id
    LIMIT 1;

    -- Check if student is enrolled in the course
    IF NOT EXISTS (
        SELECT 1 FROM course_student cs 
        WHERE cs.student_id = v_user_id AND cs.course_id = v_course_id
    ) THEN
        RAISE EXCEPTION 'Student not enrolled in course';
    END IF;

    -- Get max attempts for this task
    SELECT rt.max_attempts 
    INTO v_max_attempts
    FROM regular_tasks rt
    WHERE rt.task_id = p_task_id;

    IF v_max_attempts IS NULL THEN
        v_max_attempts := 1; -- Default for mastery tasks
    END IF;

    -- Check current attempts
    SELECT COUNT(*)::INT 
    INTO v_current_attempts
    FROM submission s
    WHERE s.student_id = v_user_id AND s.task_id = p_task_id;

    IF v_current_attempts >= v_max_attempts THEN
        RAISE EXCEPTION 'Maximum attempts exceeded for this task';
    END IF;

    -- Convert TEXT submission to JSONB for storage
    BEGIN
        v_submission_data := p_submission_text::JSONB;
    EXCEPTION WHEN others THEN
        -- If not valid JSON, wrap in text field
        v_submission_data := jsonb_build_object('text', p_submission_text);
    END;

    -- Create submission with JSONB data
    INSERT INTO submission (
        student_id,
        task_id,
        submission_data,  -- Use JSONB column
        attempt_number
    ) VALUES (
        v_user_id,
        p_task_id,
        v_submission_data,
        v_current_attempts + 1
    ) RETURNING id INTO v_submission_id;

    RETURN v_submission_id;
END;
$$;