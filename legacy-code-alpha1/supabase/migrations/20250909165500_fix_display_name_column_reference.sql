-- Fix display_name column reference to use profiles table with fallback pattern
-- Use COALESCE(NULLIF(p.full_name, ''), p.email) pattern from other functions

CREATE OR REPLACE FUNCTION public._get_submission_status_matrix_uncached(
    p_session_id TEXT,
    p_course_id UUID,
    p_unit_id UUID,
    p_section_id UUID DEFAULT NULL
) 
RETURNS TABLE(
    task_id UUID,
    task_title TEXT,
    task_type TEXT,
    task_order INTEGER,
    section_id UUID,
    section_title TEXT,
    section_order INTEGER,
    student_submissions JSONB
) 
LANGUAGE plpgsql 
SECURITY DEFINER 
AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid session';
    END IF;

    -- Check teacher authorization
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    RETURN QUERY
    SELECT 
        t.id as task_id,
        t.title as task_title,
        t.task_type,
        t.order_in_section as task_order,
        s.id as section_id,
        s.title as section_title,
        s.order_in_unit as section_order,
        COALESCE(
            json_agg(
                json_build_object(
                    'student_id', cs.student_id,
                    'student_name', COALESCE(NULLIF(p.full_name, ''), u.email),  -- Fixed: use profiles with fallback
                    'submission_id', sub.id,
                    'submitted_at', sub.submitted_at,
                    'has_teacher_feedback', sub.teacher_override_feedback IS NOT NULL,
                    'ai_grade', sub.ai_grade,
                    'teacher_grade', sub.teacher_override_grade,
                    'attempt_number', sub.attempt_number
                ) ORDER BY COALESCE(NULLIF(p.full_name, ''), u.email)  -- Fixed: order by display_name
            ) FILTER (WHERE cs.student_id IS NOT NULL), 
            '[]'::json
        )::jsonb as student_submissions
    FROM unit_section s
    LEFT JOIN task_base t ON t.section_id = s.id
    LEFT JOIN course_student cs ON cs.course_id = p_course_id
    LEFT JOIN auth.users u ON u.id = cs.student_id
    LEFT JOIN profiles p ON p.id = cs.student_id  -- Added: join profiles table
    LEFT JOIN submission sub ON sub.task_id = t.id AND sub.student_id = cs.student_id
    WHERE s.unit_id = p_unit_id
    AND (p_section_id IS NULL OR s.id = p_section_id)
    AND EXISTS (
        SELECT 1 FROM course_unit_section_status cuss
        WHERE cuss.course_id = p_course_id 
        AND cuss.section_id = s.id 
        AND cuss.is_published = TRUE
    )
    GROUP BY t.id, t.title, t.task_type, t.order_in_section, s.id, s.title, s.order_in_unit
    ORDER BY s.order_in_unit, t.order_in_section;
END;
$$;