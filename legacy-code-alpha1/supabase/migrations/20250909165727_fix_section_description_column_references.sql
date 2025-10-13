-- Fix get_published_section_details_for_student to remove non-existent s.description column
-- The unit_section table has no description column, only: id, unit_id, title, order_in_unit, materials, created_at, updated_at

CREATE OR REPLACE FUNCTION public.get_published_section_details_for_student(
    p_session_id TEXT,
    p_course_id UUID
) 
RETURNS TABLE(
    section_id UUID,
    section_title TEXT,
    section_materials JSONB,
    section_order INTEGER,
    tasks JSONB
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

    -- Check if user is student in course
    IF NOT EXISTS (
        SELECT 1 FROM course_student 
        WHERE student_id = v_user_id AND course_id = p_course_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Student not enrolled in this course';
    END IF;

    RETURN QUERY
    SELECT 
        s.id as section_id,
        s.title as section_title,
        s.materials as section_materials,
        s.order_in_unit as section_order,
        COALESCE(
            json_agg(
                json_build_object(
                    'task_id', t.id,
                    'task_title', t.title,
                    'task_instruction', t.instruction,
                    'task_type', t.task_type,
                    'task_order', t.order_in_section,
                    'assessment_criteria', t.assessment_criteria,
                    'max_attempts', CASE 
                        WHEN rt.id IS NOT NULL THEN rt.max_attempts
                        ELSE NULL
                    END,
                    'remaining_attempts', CASE 
                        WHEN rt.id IS NOT NULL THEN GREATEST(0, rt.max_attempts - COALESCE(sub_count.count, 0))
                        ELSE NULL
                    END,
                    'has_submission', sub.id IS NOT NULL,
                    'latest_submission_id', sub.id,
                    'latest_submission_at', sub.submitted_at,
                    'ai_feedback', sub.ai_feedback,
                    'ai_grade', sub.ai_grade,
                    'teacher_feedback', sub.teacher_override_feedback,  -- Fixed column reference
                    'teacher_grade', sub.teacher_override_grade,        -- Fixed column reference
                    'attempt_number', sub.attempt_number,
                    'is_mastery_task', mt.id IS NOT NULL
                ) 
                ORDER BY t.order_in_section
            ) FILTER (WHERE t.id IS NOT NULL),
            '[]'::json
        )::jsonb as tasks
    FROM unit_section s
    JOIN course_learning_unit_assignment cua ON cua.unit_id = s.unit_id
    JOIN course_unit_section_status cuss ON cuss.section_id = s.id AND cuss.course_id = p_course_id
    LEFT JOIN task_base t ON t.section_id = s.id
    LEFT JOIN regular_tasks rt ON rt.task_id = t.id
    LEFT JOIN mastery_tasks mt ON mt.task_id = t.id
    LEFT JOIN submission sub ON sub.task_id = t.id AND sub.student_id = v_user_id
    LEFT JOIN (
        SELECT task_id, COUNT(*) as count
        FROM submission
        WHERE student_id = v_user_id
        GROUP BY task_id
    ) sub_count ON sub_count.task_id = t.id
    WHERE cua.course_id = p_course_id
    AND cuss.is_published = TRUE
    GROUP BY s.id, s.title, s.materials, s.order_in_unit  -- Removed s.description from GROUP BY
    ORDER BY s.order_in_unit;
END;
$$;