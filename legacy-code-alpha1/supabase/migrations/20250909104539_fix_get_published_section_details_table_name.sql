-- Fix get_published_section_details_for_student table name
-- Problem: section_course_publication -> course_unit_section_status

BEGIN;

DROP FUNCTION IF EXISTS public.get_published_section_details_for_student(TEXT, UUID, UUID);
DROP FUNCTION IF EXISTS public.get_published_section_details_for_student(TEXT, UUID, UUID, UUID);
CREATE FUNCTION public.get_published_section_details_for_student(
    p_session_id TEXT,
    p_unit_id UUID,
    p_course_id UUID
)
RETURNS TABLE(
    section_id uuid,
    section_title text,
    section_order integer,
    materials jsonb,
    tasks jsonb
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

    -- Students must be enrolled; teachers can access if authorized
    IF v_user_role = 'student' THEN
        IF NOT EXISTS (
            SELECT 1 FROM course_student cs 
            WHERE cs.course_id = p_course_id AND cs.student_id = v_user_id
        ) THEN
            RETURN;
        END IF;
    ELSIF v_user_role = 'teacher' THEN
        IF NOT EXISTS (
            SELECT 1 FROM course c 
            WHERE c.id = p_course_id 
            AND (c.creator_id = v_user_id OR EXISTS (
                SELECT 1 FROM course_teacher ct 
                WHERE ct.course_id = p_course_id AND ct.teacher_id = v_user_id
            ))
        ) THEN
            RETURN;
        END IF;
    ELSE
        RETURN;
    END IF;

    -- Return published sections with details using CORRECT table name
    RETURN QUERY
    SELECT 
        us.id as section_id,
        us.title as section_title,
        us.order_in_unit as section_order,
        us.materials,
        COALESCE(
            (SELECT jsonb_agg(task_info)
             FROM (
                 SELECT jsonb_build_object(
                     'id', t.id,
                     'title', t.title,
                     'task_type', t.task_type,
                     'order_in_section', t.order_in_section,
                     'prompt', COALESCE(rt.prompt, mt.prompt),
                     'max_attempts', rt.max_attempts,
                     'grading_criteria', rt.grading_criteria,
                     'is_mastery', CASE WHEN mt.task_id IS NOT NULL THEN TRUE ELSE FALSE END,
                     'difficulty_level', mt.difficulty_level,
                     'concept_explanation', mt.concept_explanation
                 ) as task_info
                 FROM task_base t
                 LEFT JOIN regular_tasks rt ON rt.task_id = t.id
                 LEFT JOIN mastery_tasks mt ON mt.task_id = t.id
                 WHERE t.section_id = us.id
                 ORDER BY t.order_in_section
             ) task_subquery), 
            '[]'::jsonb
        ) as tasks
    FROM unit_section us
    JOIN course_unit_section_status cuss ON cuss.section_id = us.id AND cuss.course_id = p_course_id
    WHERE us.unit_id = p_unit_id 
    AND cuss.is_published = TRUE
    ORDER BY us.order_in_unit;
END;
$$;

COMMIT;

GRANT EXECUTE ON FUNCTION public.get_published_section_details_for_student TO anon;