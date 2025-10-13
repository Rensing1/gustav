-- Fix remaining created_by schema issues
-- Problem: _get_submission_status_matrix_uncached still references created_by instead of creator_id

BEGIN;

-- Fix _get_submission_status_matrix_uncached: Replace created_by with creator_id
CREATE OR REPLACE FUNCTION public._get_submission_status_matrix_uncached(
    p_session_id TEXT,
    p_course_id UUID,
    p_unit_id UUID
)
RETURNS TABLE (
    student_id UUID,
    student_email TEXT,
    student_name TEXT,
    task_statuses JSONB
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

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can view submission matrix';
    END IF;

    -- Check teacher authorization - FIX: Use creator_id instead of created_by
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Build the matrix of student submissions per task
    RETURN QUERY
    WITH enrolled_students AS (
        SELECT 
            cs.student_id,
            p.email,
            COALESCE(NULLIF(p.full_name, ''), p.email) as display_name
        FROM course_student cs
        JOIN profiles p ON p.id = cs.student_id
        WHERE cs.course_id = p_course_id
    ),
    unit_tasks AS (
        SELECT 
            t.id as task_id,
            t.title,
            t.order_in_section,
            s.order_in_unit,
            s.id as section_id
        FROM task_base t
        JOIN unit_section s ON s.id = t.section_id
        WHERE s.unit_id = p_unit_id
    ),
    submission_status AS (
        SELECT 
            es.student_id,
            ut.task_id,
            jsonb_build_object(
                'task_id', ut.task_id,
                'task_title', ut.title,
                'section_id', ut.section_id,
                'has_submission', EXISTS(
                    SELECT 1 FROM submission sub 
                    WHERE sub.student_id = es.student_id 
                    AND sub.task_id = ut.task_id
                ),
                'is_correct', (
                    SELECT BOOL_OR(sub.is_correct) 
                    FROM submission sub 
                    WHERE sub.student_id = es.student_id 
                    AND sub.task_id = ut.task_id
                ),
                'submission_count', (
                    SELECT COUNT(*) 
                    FROM submission sub 
                    WHERE sub.student_id = es.student_id 
                    AND sub.task_id = ut.task_id
                ),
                'latest_submission_at', (
                    SELECT MAX(sub.submitted_at) 
                    FROM submission sub 
                    WHERE sub.student_id = es.student_id 
                    AND sub.task_id = ut.task_id
                ),
                'has_feedback', EXISTS(
                    SELECT 1 FROM submission sub 
                    WHERE sub.student_id = es.student_id 
                    AND sub.task_id = ut.task_id
                    AND (sub.ai_feedback IS NOT NULL OR sub.teacher_feedback IS NOT NULL)
                )
            ) as status_data,
            ut.order_in_unit * 1000 + ut.order_in_section as sort_order
        FROM enrolled_students es
        CROSS JOIN unit_tasks ut
    )
    SELECT 
        es.student_id,
        es.email as student_email,
        es.display_name as student_name,
        COALESCE(
            jsonb_object_agg(
                ss.task_id::TEXT,
                ss.status_data
            ) FILTER (WHERE ss.status_data IS NOT NULL),
            '{}'::jsonb
        ) as task_statuses
    FROM enrolled_students es
    LEFT JOIN submission_status ss ON ss.student_id = es.student_id
    GROUP BY es.student_id, es.email, es.display_name
    ORDER BY es.email;
END;
$$;

COMMIT;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION public._get_submission_status_matrix_uncached TO anon;