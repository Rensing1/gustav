-- Fix get_submission_status_matrix function - change 'courses' to 'course' table name

-- Drop the existing function
DROP FUNCTION IF EXISTS public._get_submission_status_matrix_uncached(TEXT, UUID, UUID);

-- Recreate _get_submission_status_matrix_uncached with correct table name
CREATE FUNCTION public._get_submission_status_matrix_uncached(
    p_session_id TEXT,
    p_course_id UUID,
    p_unit_id UUID
)
RETURNS JSONB
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_result JSONB;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid THEN
        RAISE EXCEPTION 'Invalid session';
    END IF;
    
    -- Check authorization
    IF v_user_role = 'teacher' THEN
        -- Teacher must be course creator
        IF NOT EXISTS (
            SELECT 1 FROM course -- Changed from 'courses' to 'course'
            WHERE id = p_course_id AND creator_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Unauthorized access to course';
        END IF;
    ELSE
        RAISE EXCEPTION 'Only teachers can access submission matrix';
    END IF;
    
    -- Build the submission matrix
    WITH enrolled_students AS (
        SELECT 
            cs.student_id,
            COALESCE(p.display_name, u.email::text) as student_name  -- Cast email to text
        FROM course_student cs
        JOIN auth.users u ON u.id = cs.student_id
        LEFT JOIN profiles p ON p.id = cs.student_id
        WHERE cs.course_id = p_course_id
    ),
    unit_tasks AS (
        SELECT 
            t.id as task_id,
            t.instruction as task_title,  -- Use instruction instead of title
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
                'task_title', ut.task_title,
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
                'latest_submission_id', (
                    SELECT sub.id 
                    FROM submission sub 
                    WHERE sub.student_id = es.student_id 
                    AND sub.task_id = ut.task_id
                    ORDER BY sub.timestamp DESC
                    LIMIT 1
                )
            ) as submission_info
        FROM enrolled_students es
        CROSS JOIN unit_tasks ut
    )
    SELECT jsonb_build_object(
        'students', (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'id', student_id,
                    'name', student_name
                ) ORDER BY student_name
            ) FROM enrolled_students
        ),
        'tasks', (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'id', task_id,
                    'title', task_title,
                    'section_id', section_id
                ) ORDER BY order_in_unit, order_in_section
            ) FROM unit_tasks
        ),
        'submissions', (
            SELECT jsonb_object_agg(
                student_id::text,
                (
                    SELECT jsonb_object_agg(
                        task_id::text,
                        submission_info
                    )
                    FROM submission_status ss2
                    WHERE ss2.student_id = ss.student_id
                )
            ) FROM (SELECT DISTINCT student_id FROM submission_status) ss
        )
    ) INTO v_result;
    
    RETURN COALESCE(v_result, '{}'::jsonb);
END;
$$;