-- Fix get_published_section_details_for_student to use course_unit_section_status instead of section_publishing
-- The section_publishing table was replaced with course_unit_section_status during a previous migration

-- Drop the old function versions first
DROP FUNCTION IF EXISTS public.get_published_section_details_for_student(TEXT, UUID);
DROP FUNCTION IF EXISTS public.get_published_section_details_for_student(TEXT, UUID, UUID, UUID);

-- Create the corrected function
CREATE OR REPLACE FUNCTION public.get_published_section_details_for_student(
    p_session_id TEXT,
    p_course_id UUID
)
RETURNS TABLE (
    id UUID,
    title TEXT,
    order_in_unit INTEGER,
    materials JSON,
    tasks JSON
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

    -- Check if student is enrolled in course
    IF v_user_role = 'student' THEN
        IF NOT EXISTS (
            SELECT 1 FROM course_student
            WHERE course_id = p_course_id AND student_id = v_user_id
        ) THEN
            RETURN;
        END IF;
    END IF;

    -- Return published sections with tasks
    RETURN QUERY
    WITH published_sections AS (
        SELECT 
            s.id,
            s.title,
            s.order_in_unit,
            s.materials,
            cuss.published_at
        FROM unit_section s
        -- Use course_unit_section_status instead of section_publishing
        JOIN course_unit_section_status cuss ON s.id = cuss.section_id
        JOIN learning_unit u ON s.unit_id = u.id
        JOIN course_learning_unit_assignment cua ON u.id = cua.unit_id
        WHERE cua.course_id = p_course_id 
            AND cuss.course_id = p_course_id
            AND cuss.is_published = true  -- Only published sections
    )
    SELECT 
        ps.id,
        ps.title,
        ps.order_in_unit,
        ps.materials::json,
        COALESCE(
            (SELECT json_agg(
                json_build_object(
                    'id', t.id,
                    'title', t.title,
                    'instruction', t.instruction,
                    'task_type', t.task_type,
                    'is_mastery', CASE WHEN mt.task_id IS NOT NULL THEN TRUE ELSE FALSE END,
                    'max_attempts', rt.max_attempts,
                    'difficulty_level', mt.difficulty_level,
                    'solution_hints', t.solution_hints
                )
                ORDER BY t.order_in_section
            )
            FROM task_base t
            LEFT JOIN regular_tasks rt ON rt.task_id = t.id
            LEFT JOIN mastery_tasks mt ON mt.task_id = t.id
            WHERE t.section_id = ps.id
            ), '[]'::json
        ) as tasks
    FROM published_sections ps
    ORDER BY ps.order_in_unit;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_published_section_details_for_student(TEXT, UUID) TO anon;

-- Add comment
COMMENT ON FUNCTION public.get_published_section_details_for_student(TEXT, UUID) IS 'Returns published sections for a course. Updated to use course_unit_section_status instead of deprecated section_publishing table.';
