-- Fix create_section to use unit_id instead of learning_unit_id and remove description parameter

DROP FUNCTION IF EXISTS public.create_section(TEXT, UUID, TEXT, TEXT, JSONB);
CREATE OR REPLACE FUNCTION public.create_section(
    p_session_id TEXT,
    p_unit_id UUID,
    p_title TEXT,
    p_description TEXT DEFAULT NULL,  -- Keep parameter for compatibility but don't use it
    p_materials JSONB DEFAULT NULL
)
RETURNS UUID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_section_id UUID;
    v_order_in_unit INT;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can create sections';
    END IF;

    -- Check if teacher owns the learning unit
    IF NOT EXISTS (
        SELECT 1 FROM learning_unit 
        WHERE id = p_unit_id AND creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Get next order position
    SELECT COALESCE(MAX(order_in_unit), 0) + 1
    INTO v_order_in_unit
    FROM unit_section
    WHERE unit_id = p_unit_id;  -- Fixed: changed learning_unit_id to unit_id

    -- Create section (without description since column doesn't exist)
    INSERT INTO unit_section (
        unit_id,  -- Fixed: changed from learning_unit_id
        title,
        materials,
        order_in_unit
    )
    VALUES (
        p_unit_id,
        p_title,
        p_materials,
        v_order_in_unit
    )
    RETURNING id INTO v_section_id;

    RETURN v_section_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.create_section TO anon;

-- Also fix update_section_materials to use correct join
DROP FUNCTION IF EXISTS public.update_section_materials(TEXT, UUID, JSONB);
CREATE OR REPLACE FUNCTION public.update_section_materials(
    p_session_id TEXT,
    p_section_id UUID,
    p_materials JSONB
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
        RAISE EXCEPTION 'Unauthorized: Only teachers can update section materials';
    END IF;

    -- Check if teacher owns the section's learning unit
    IF NOT EXISTS (
        SELECT 1 
        FROM unit_section s
        JOIN learning_unit lu ON lu.id = s.unit_id  -- Fixed: changed from learning_unit_id
        WHERE s.id = p_section_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Update materials
    UPDATE unit_section
    SET 
        materials = p_materials,
        updated_at = NOW()
    WHERE id = p_section_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.update_section_materials TO anon;

-- Also fix functions that reference unit_section to use unit_id
-- Fix get_published_section_details_for_student
DROP FUNCTION IF EXISTS public.get_published_section_details_for_student(TEXT, UUID, UUID, UUID);
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
            NULL::TEXT as description,  -- No description column in unit_section
            s.materials,
            s.order_in_unit,
            COALESCE(cps.is_published, FALSE) as is_published
        FROM unit_section s
        LEFT JOIN course_publish_state cps ON 
            cps.section_id = s.id AND 
            cps.course_id = p_course_id
        WHERE s.unit_id = p_unit_id  -- Fixed: changed learning_unit_id to unit_id
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

GRANT EXECUTE ON FUNCTION public.get_published_section_details_for_student TO anon;

-- Fix other functions that use unit_section
DROP FUNCTION IF EXISTS public.get_submissions_for_course_and_unit(TEXT, UUID, UUID);
CREATE OR REPLACE FUNCTION public.get_submissions_for_course_and_unit(
    p_session_id TEXT,
    p_course_id UUID,
    p_unit_id UUID
)
RETURNS TABLE (
    submission_id UUID,
    student_id UUID,
    student_email TEXT,
    student_name TEXT,
    task_id UUID,
    task_title TEXT,
    section_id UUID,
    section_title TEXT,
    submission_text TEXT,
    is_correct BOOLEAN,
    submitted_at TIMESTAMPTZ,
    ai_feedback TEXT,
    teacher_feedback TEXT,
    override_grade BOOLEAN
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
        RAISE EXCEPTION 'Unauthorized: Only teachers can view submissions';
    END IF;

    -- Check if teacher is authorized for this course
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Return submissions for the course and unit
    RETURN QUERY
    SELECT 
        sub.id as submission_id,
        sub.student_id,
        p.email as student_email,
        COALESCE(p.display_name, SPLIT_PART(p.email, '@', 1)) as student_name,
        sub.task_id,
        t.title as task_title,
        s.id as section_id,
        s.title as section_title,
        sub.submission_text,
        sub.is_correct,
        sub.submitted_at,
        sub.ai_feedback,
        sub.teacher_feedback,
        sub.override_grade
    FROM submission sub
    JOIN task_base t ON t.id = sub.task_id
    JOIN unit_section s ON s.id = t.section_id
    JOIN profiles p ON p.id = sub.student_id
    WHERE s.unit_id = p_unit_id  -- Fixed: changed learning_unit_id to unit_id
    AND EXISTS (
        SELECT 1 FROM course_student cs
        WHERE cs.student_id = sub.student_id 
        AND cs.course_id = p_course_id
    )
    ORDER BY s.order_in_unit, t.order_in_section, sub.submitted_at DESC;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_submissions_for_course_and_unit TO anon;

-- Fix _get_submission_status_matrix_uncached
DROP FUNCTION IF EXISTS public._get_submission_status_matrix_uncached(TEXT, UUID, UUID);
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

    -- Build the matrix of student submissions per task
    RETURN QUERY
    WITH enrolled_students AS (
        SELECT 
            cs.student_id,
            p.email,
            COALESCE(p.display_name, SPLIT_PART(p.email, '@', 1)) as display_name
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
        WHERE s.unit_id = p_unit_id  -- Fixed: changed learning_unit_id to unit_id
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

GRANT EXECUTE ON FUNCTION public._get_submission_status_matrix_uncached TO anon;

-- Fix get_section_statuses_for_unit_in_course  
DROP FUNCTION IF EXISTS public.get_section_statuses_for_unit_in_course(TEXT, UUID, UUID);
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
        WHERE id = p_course_id AND creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Get section statuses
    RETURN QUERY
    SELECT 
        s.id as section_id,
        s.title as section_title,
        s.order_in_unit,
        COALESCE(cps.is_published, FALSE) as is_published,
        COUNT(DISTINCT t.id)::INT as task_count,
        cps.published_at
    FROM unit_section s
    LEFT JOIN course_publish_state cps ON 
        cps.section_id = s.id AND 
        cps.course_id = p_course_id
    LEFT JOIN task_base t ON t.section_id = s.id
    WHERE s.unit_id = p_unit_id  -- Fixed: changed learning_unit_id to unit_id
    GROUP BY s.id, s.title, s.order_in_unit, cps.is_published, cps.published_at
    ORDER BY s.order_in_unit;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_section_statuses_for_unit_in_course TO anon;

-- Fix publish_section_for_course
DROP FUNCTION IF EXISTS public.publish_section_for_course(TEXT, UUID, UUID);
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
        WHERE id = p_course_id AND creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Verify section belongs to a unit assigned to this course
    IF NOT EXISTS (
        SELECT 1 
        FROM unit_section s
        JOIN course_learning_unit_assignment cua ON cua.unit_id = s.unit_id  -- Fixed: both sides use unit_id
        WHERE s.id = p_section_id AND cua.course_id = p_course_id
    ) THEN
        RAISE EXCEPTION 'Section does not belong to a unit assigned to this course';
    END IF;

    -- Insert or update publish state
    INSERT INTO course_publish_state (
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

GRANT EXECUTE ON FUNCTION public.publish_section_for_course TO anon;