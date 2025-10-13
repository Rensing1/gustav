-- Fix update_submission_teacher_override: column sec.learning_unit_id does not exist
-- The correct column in unit_section table is 'unit_id', not 'learning_unit_id'

CREATE OR REPLACE FUNCTION public.update_submission_teacher_override(
    p_session_id TEXT,
    p_submission_id UUID,
    p_override_grade BOOLEAN,
    p_teacher_feedback TEXT
)
RETURNS VOID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_student_id UUID;
    v_task_id UUID;
    v_course_id UUID;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can override grades';
    END IF;

    -- Get submission info
    SELECT s.student_id, s.task_id
    INTO v_student_id, v_task_id
    FROM submission s
    WHERE s.id = p_submission_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Submission not found';
    END IF;

    -- Check if teacher has access to this course - FIXED: sec.unit_id instead of sec.learning_unit_id
    SELECT cua.course_id
    INTO v_course_id
    FROM task_base t
    JOIN unit_section sec ON sec.id = t.section_id
    JOIN learning_unit lu ON lu.id = sec.unit_id  -- FIXED: was sec.learning_unit_id
    JOIN course_learning_unit_assignment cua ON cua.unit_id = lu.id  -- FIXED: was cua.learning_unit_id 
    WHERE t.id = v_task_id
    LIMIT 1;

    IF NOT EXISTS (
        SELECT 1 FROM course_teacher ct
        WHERE ct.teacher_id = v_user_id AND ct.course_id = v_course_id
    ) AND NOT EXISTS (
        -- Also allow if teacher created the learning unit directly
        SELECT 1 FROM learning_unit lu
        JOIN unit_section sec ON sec.unit_id = lu.id  -- FIXED: was sec.learning_unit_id
        JOIN task_base t ON t.section_id = sec.id
        WHERE t.id = v_task_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course or learning unit';
    END IF;

    -- Update submission with teacher override
    UPDATE submission
    SET 
        teacher_override_grade = CASE 
            WHEN p_override_grade THEN 'correct'::TEXT 
            ELSE 'incorrect'::TEXT 
        END,
        teacher_override_feedback = p_teacher_feedback,
        updated_at = NOW()
    WHERE id = p_submission_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Failed to update submission';
    END IF;
END;
$$;