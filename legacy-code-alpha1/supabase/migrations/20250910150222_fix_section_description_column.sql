-- Fix get_published_section_details_for_student - remove reference to non-existent description column

DROP FUNCTION IF EXISTS public.get_published_section_details_for_student(TEXT, UUID, UUID, UUID);

CREATE FUNCTION public.get_published_section_details_for_student(
    p_session_id TEXT,
    p_course_id UUID,
    p_unit_id UUID,
    p_student_id UUID
)
RETURNS TABLE (
    section_id UUID,
    section_title TEXT,
    section_description TEXT,
    section_materials JSONB,
    order_in_unit INTEGER,
    is_published BOOLEAN,
    tasks JSONB
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
        RAISE EXCEPTION 'Invalid session';
    END IF;
    
    -- For teacher, verify they own the course
    IF v_user_role = 'teacher' AND v_user_id != p_student_id THEN
        IF NOT EXISTS (
            SELECT 1 FROM course 
            WHERE id = p_course_id AND creator_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Unauthorized access to student data';
        END IF;
    -- For student, verify they can only access their own data
    ELSIF v_user_role = 'student' AND v_user_id != p_student_id THEN
        RAISE EXCEPTION 'Students can only access their own data';
    END IF;

    -- Complex query to get section details with tasks and submission status
    RETURN QUERY
    WITH published_sections AS (
        SELECT 
            s.id,
            s.title,
            NULL::TEXT as description,  -- unit_section table has no description column
            s.materials,
            s.order_in_unit,
            COALESCE(cuss.is_published, FALSE) as is_published
        FROM unit_section s
        LEFT JOIN course_unit_section_status cuss ON 
            cuss.section_id = s.id AND 
            cuss.course_id = p_course_id
        WHERE s.unit_id = p_unit_id
    ),
    section_tasks AS (
        SELECT 
            ps.id as section_id,
            jsonb_agg(
                jsonb_build_object(
                    'task_id', tb.id,
                    'task_title', tb.instruction,
                    'task_type', tb.task_type,
                    'order_in_section', tb.order_in_section,
                    'max_attempts', CASE 
                        WHEN tb.task_type = 'regular_task' THEN 3
                        ELSE NULL
                    END,
                    'has_submission', EXISTS(
                        SELECT 1 FROM submission sub
                        WHERE sub.task_id = tb.id 
                        AND sub.student_id = p_student_id
                    ),
                    'is_correct', (
                        SELECT is_correct
                        FROM submission sub
                        WHERE sub.task_id = tb.id 
                        AND sub.student_id = p_student_id
                        ORDER BY sub.submitted_at DESC
                        LIMIT 1
                    ),
                    'remaining_attempts', CASE 
                        WHEN tb.task_type = 'regular_task' THEN 
                            3 - COALESCE((
                                SELECT COUNT(*)
                                FROM submission sub
                                WHERE sub.task_id = tb.id 
                                AND sub.student_id = p_student_id
                            ), 0)
                        ELSE NULL
                    END
                ) ORDER BY tb.order_in_section
            ) as tasks
        FROM published_sections ps
        JOIN task_base tb ON tb.section_id = ps.id
        WHERE ps.is_published = TRUE
        GROUP BY ps.id
    )
    SELECT 
        ps.id as section_id,
        ps.title as section_title,
        ps.description as section_description,  -- Will be NULL
        ps.materials as section_materials,
        ps.order_in_unit,
        ps.is_published,
        COALESCE(st.tasks, '[]'::jsonb) as tasks
    FROM published_sections ps
    LEFT JOIN section_tasks st ON st.section_id = ps.id
    WHERE ps.is_published = TRUE
    ORDER BY ps.order_in_unit;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_published_section_details_for_student(TEXT, UUID, UUID, UUID) TO anon;