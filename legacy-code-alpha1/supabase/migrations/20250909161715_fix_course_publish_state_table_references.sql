-- Fix references from course_publish_state to course_unit_section_status
-- The table was incorrectly referenced in multiple functions

-- 1. Fix get_published_section_details_for_student
CREATE OR REPLACE FUNCTION public.get_published_section_details_for_student(
    p_session_id TEXT,
    p_student_id UUID,
    p_unit_id UUID,
    p_course_id UUID
)
RETURNS TABLE (
    section_id UUID,
    section_title TEXT,
    section_description TEXT,
    section_materials JSONB,
    order_in_unit INT,
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
        RETURN;
    END IF;

    -- Check permissions: student must be self, teacher can see all
    IF v_user_role = 'student' AND v_user_id != p_student_id THEN
        RETURN;
    END IF;

    -- Complex query to get section details with tasks and submission status
    RETURN QUERY
    WITH published_sections AS (
        SELECT 
            s.id,
            s.title,
            s.description,
            s.materials,
            s.order_in_unit,
            COALESCE(cuss.is_published, FALSE) as is_published
        FROM unit_section s
        LEFT JOIN course_unit_section_status cuss ON 
            cuss.section_id = s.id AND 
            cuss.course_id = p_course_id
        WHERE s.learning_unit_id = p_unit_id
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
                'max_attempts', t.max_attempts,
                'prompt', t.prompt,
                'submission_count', COUNT(sub.id),
                'attempts_remaining', GREATEST(0, t.max_attempts - COUNT(sub.id)),
                'latest_submission', 
                CASE 
                    WHEN COUNT(sub.id) > 0 THEN
                        jsonb_build_object(
                            'id', MAX(sub.id),
                            'is_correct', BOOL_OR(sub.is_correct),
                            'submitted_at', MAX(sub.submitted_at),
                            'has_feedback', MAX(sub.ai_feedback) IS NOT NULL OR MAX(sub.teacher_feedback) IS NOT NULL,
                            'feedback_viewed', MAX(sub.feedback_viewed_at) IS NOT NULL
                        )
                    ELSE NULL
                END
            ) as task_data
        FROM all_regular_tasks t
        LEFT JOIN submission sub ON 
            sub.task_id = t.id AND 
            sub.student_id = p_student_id
        GROUP BY t.id, t.section_id, t.title, t.task_type, t.order_in_section, t.max_attempts, t.prompt
    )
    SELECT 
        ps.id as section_id,
        ps.title as section_title,
        ps.description as section_description,
        ps.materials as section_materials,
        ps.order_in_unit,
        ps.is_published,
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
    GROUP BY ps.id, ps.title, ps.description, ps.materials, ps.order_in_unit, ps.is_published
    ORDER BY ps.order_in_unit;
END;
$$;

-- 2. Fix get_section_statuses_for_unit_in_course
CREATE OR REPLACE FUNCTION public.get_section_statuses_for_unit_in_course(
    p_session_id TEXT,
    p_unit_id UUID,
    p_course_id UUID
)
RETURNS TABLE (
    section_id UUID,
    section_title TEXT,
    order_in_unit INT,
    is_published BOOLEAN,
    task_count INT,
    published_at TIMESTAMPTZ
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
        RAISE EXCEPTION 'Unauthorized: Only teachers can view section statuses';
    END IF;

    -- Check teacher authorization
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND created_by = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Get section statuses
    RETURN QUERY
    SELECT 
        s.id as section_id,
        s.title as section_title,
        s.order_in_unit,
        COALESCE(cuss.is_published, FALSE) as is_published,
        COUNT(DISTINCT t.id)::INT as task_count,
        cuss.published_at
    FROM unit_section s
    LEFT JOIN course_unit_section_status cuss ON 
        cuss.section_id = s.id AND 
        cuss.course_id = p_course_id
    LEFT JOIN task_base t ON t.section_id = s.id
    WHERE s.learning_unit_id = p_unit_id
    GROUP BY s.id, s.title, s.order_in_unit, cuss.is_published, cuss.published_at
    ORDER BY s.order_in_unit;
END;
$$;

-- 3. Fix publish_section_for_course
CREATE OR REPLACE FUNCTION public.publish_section_for_course(
    p_session_id TEXT,
    p_section_id UUID,
    p_course_id UUID
)
RETURNS VOID
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
        RAISE EXCEPTION 'Unauthorized: Only teachers can publish sections';
    END IF;

    -- Check teacher authorization
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND created_by = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Verify section belongs to a unit assigned to this course
    IF NOT EXISTS (
        SELECT 1 
        FROM unit_section s
        JOIN course_learning_unit_assignment cua ON cua.learning_unit_id = s.learning_unit_id
        WHERE s.id = p_section_id AND cua.course_id = p_course_id
    ) THEN
        RAISE EXCEPTION 'Section does not belong to a unit assigned to this course';
    END IF;

    -- Insert or update publish state
    INSERT INTO course_unit_section_status (
        course_id,
        section_id,
        is_published,
        published_at
    )
    VALUES (
        p_course_id,
        p_section_id,
        TRUE,
        NOW()
    )
    ON CONFLICT (course_id, section_id) 
    DO UPDATE SET
        is_published = TRUE,
        published_at = NOW();
END;
$$;

-- 4. Fix unpublish_section_for_course
CREATE OR REPLACE FUNCTION public.unpublish_section_for_course(
    p_session_id TEXT,
    p_section_id UUID,
    p_course_id UUID
)
RETURNS VOID
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
        RAISE EXCEPTION 'Unauthorized: Only teachers can unpublish sections';
    END IF;

    -- Check teacher authorization
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND created_by = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Update publish state
    UPDATE course_unit_section_status
    SET is_published = FALSE
    WHERE course_id = p_course_id 
    AND section_id = p_section_id;
END;
$$;