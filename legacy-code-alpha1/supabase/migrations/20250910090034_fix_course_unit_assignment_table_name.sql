-- Fix table name in get_published_section_details_for_student
-- The function references course_unit_assignment but the actual table is course_learning_unit_assignment

-- Drop and recreate the 2-parameter function with correct table name
DROP FUNCTION IF EXISTS public.get_published_section_details_for_student(TEXT, UUID);

CREATE OR REPLACE FUNCTION public.get_published_section_details_for_student(
    p_session_id TEXT,
    p_course_id UUID
)
RETURNS TABLE (
    section_id UUID,
    section_title TEXT,
    section_materials JSONB,
    section_order INTEGER,
    tasks JSONB
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_unit_id UUID;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Get the unit_id from course_learning_unit_assignment for this course
    SELECT unit_id INTO v_unit_id
    FROM course_learning_unit_assignment
    WHERE course_id = p_course_id
    LIMIT 1;

    IF v_unit_id IS NULL THEN
        RETURN;
    END IF;

    -- Only allow students to see their own data
    IF v_user_role = 'student' THEN
        -- Check if student is enrolled in the course
        IF NOT EXISTS (
            SELECT 1 FROM course_student 
            WHERE student_id = v_user_id AND course_id = p_course_id
        ) THEN
            RETURN;
        END IF;
    END IF;

    -- Get section details with proper column references
    RETURN QUERY
    WITH published_sections AS (
        SELECT 
            s.id,
            s.title,
            s.materials,
            s.order_in_unit,
            COALESCE(cuss.is_published, FALSE) as is_published
        FROM unit_section s
        LEFT JOIN course_unit_section_status cuss ON 
            cuss.section_id = s.id AND 
            cuss.course_id = p_course_id
        WHERE s.unit_id = v_unit_id
    ),
    task_details AS (
        -- Get regular tasks with submission info
        SELECT 
            t.section_id,
            jsonb_build_object(
                'id', t.id,
                'title', t.title,
                'task_type', t.task_type,
                'order_in_section', t.order_in_section,
                'is_mastery', FALSE,
                'max_attempts', COALESCE(rt.max_attempts, 1),
                'prompt', COALESCE(rt.prompt, ''),
                'submission_count', COUNT(sub.id),
                'attempts_remaining', GREATEST(0, COALESCE(rt.max_attempts, 1) - COUNT(sub.id)),
                'latest_submission', 
                CASE 
                    WHEN COUNT(sub.id) > 0 THEN
                        jsonb_build_object(
                            'id', MAX(sub.id)::TEXT,
                            'is_correct', BOOL_OR(sub.is_correct),
                            'submitted_at', MAX(sub.submitted_at),
                            'has_feedback', MAX(sub.ai_feedback) IS NOT NULL OR MAX(sub.teacher_override_feedback) IS NOT NULL,
                            'feedback_viewed', MAX(sub.feedback_viewed_at) IS NOT NULL
                        )
                    ELSE NULL
                END
            ) as task_data
        FROM task_base t
        LEFT JOIN regular_tasks rt ON rt.task_id = t.id
        LEFT JOIN submission sub ON 
            sub.task_id = t.id AND 
            sub.student_id = v_user_id
        WHERE t.task_type = 'regular'
        GROUP BY t.id, t.section_id, t.title, t.task_type, t.order_in_section, rt.max_attempts, rt.prompt
    )
    SELECT 
        ps.id as section_id,
        ps.title as section_title,
        ps.materials as section_materials,
        ps.order_in_unit as section_order,
        COALESCE(
            jsonb_agg(
                td.task_data 
                ORDER BY (td.task_data->>'order_in_section')::INT
            ) FILTER (WHERE td.task_data IS NOT NULL),
            '[]'::jsonb
        ) as tasks
    FROM published_sections ps
    LEFT JOIN task_details td ON td.section_id = ps.id
    WHERE ps.is_published = TRUE OR v_user_role = 'teacher'
    GROUP BY ps.id, ps.title, ps.materials, ps.order_in_unit, ps.is_published
    ORDER BY ps.order_in_unit;
END;
$$;