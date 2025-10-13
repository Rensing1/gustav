-- Fix submission and mastery table column references after HttpOnly migration

-- 1. Fix get_submission_status_matrix - use submitted_at instead of timestamp
DROP FUNCTION IF EXISTS public._get_submission_status_matrix_uncached(TEXT, UUID, UUID);

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
            SELECT 1 FROM course 
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
            COALESCE(p.full_name, u.email::text) as student_name
        FROM course_student cs
        JOIN auth.users u ON u.id = cs.student_id
        LEFT JOIN profiles p ON p.id = cs.student_id
        WHERE cs.course_id = p_course_id
    ),
    unit_tasks AS (
        SELECT 
            t.id as task_id,
            t.instruction as task_title,
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
                    ORDER BY sub.submitted_at DESC  -- Changed from timestamp to submitted_at
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

-- 2. Fix get_submissions_for_course_and_unit - use submitted_at and correct column names
DROP FUNCTION IF EXISTS public.get_submissions_for_course_and_unit(TEXT, UUID, UUID);

CREATE FUNCTION public.get_submissions_for_course_and_unit(
    p_session_id TEXT,
    p_course_id UUID,
    p_unit_id UUID
)
RETURNS TABLE (
    student_id UUID,
    student_name TEXT,
    section_id UUID,
    section_title TEXT,
    task_id UUID,
    task_title TEXT,
    task_type TEXT,
    submission_id UUID,
    is_correct BOOLEAN,
    submitted_at TIMESTAMP WITH TIME ZONE,
    ai_feedback TEXT,
    teacher_feedback TEXT,
    teacher_override BOOLEAN
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
    
    -- Check authorization
    IF v_user_role = 'teacher' THEN
        -- Teacher must be course creator
        IF NOT EXISTS (
            SELECT 1 FROM course 
            WHERE id = p_course_id AND creator_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Unauthorized access to course';
        END IF;
    ELSE
        RAISE EXCEPTION 'Only teachers can access all submissions';
    END IF;
    
    -- Get all submissions for the unit and course
    RETURN QUERY
    WITH course_students AS (
        SELECT 
            cs.student_id,
            COALESCE(p.full_name, u.email::text) as student_name
        FROM course_student cs
        JOIN auth.users u ON u.id = cs.student_id
        LEFT JOIN profiles p ON p.id = cs.student_id
        WHERE cs.course_id = p_course_id
    ),
    unit_tasks AS (
        SELECT 
            tb.id as task_id,
            tb.instruction as task_title,
            tb.task_type,
            tb.section_id,
            s.title as section_title
        FROM task_base tb
        JOIN unit_section s ON s.id = tb.section_id
        WHERE s.unit_id = p_unit_id
    )
    SELECT 
        cs.student_id,
        cs.student_name,
        ut.section_id,
        ut.section_title,
        ut.task_id,
        ut.task_title,
        ut.task_type,
        sub.id as submission_id,
        sub.is_correct,
        sub.submitted_at,  -- Already correct column name
        sub.ai_feedback,
        sub.teacher_override_feedback as teacher_feedback,  -- Map to correct column
        CASE WHEN sub.teacher_override_grade IS NOT NULL THEN TRUE ELSE FALSE END as teacher_override  -- Derive from grade
    FROM course_students cs
    CROSS JOIN unit_tasks ut
    LEFT JOIN submission sub ON 
        sub.student_id = cs.student_id AND 
        sub.task_id = ut.task_id
    ORDER BY cs.student_name, ut.section_id, ut.task_id, sub.submitted_at DESC;
END;
$$;

-- 3. Fix get_published_section_details_for_student - complete the tasks JSONB
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
            s.description,
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
                    'task_title', tb.instruction,  -- Use instruction instead of title
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
        ps.description as section_description,
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

-- 4. Fix get_section_tasks - ensure proper return type for task IDs
DROP FUNCTION IF EXISTS public.get_section_tasks(TEXT, UUID);

CREATE FUNCTION public.get_section_tasks(
    p_session_id TEXT,
    p_section_id UUID
)
RETURNS TABLE (
    task_id UUID,
    instruction TEXT,
    task_type TEXT,
    order_in_section INTEGER,
    created_at TIMESTAMP WITH TIME ZONE
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
    
    -- Only teachers need explicit authorization check
    IF v_user_role = 'teacher' THEN
        IF NOT EXISTS (
            SELECT 1 FROM unit_section us
            JOIN learning_unit lu ON us.unit_id = lu.id
            WHERE us.id = p_section_id AND lu.creator_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Unauthorized access to section';
        END IF;
    END IF;
    
    -- Return tasks for the section
    RETURN QUERY
    SELECT 
        tb.id::UUID as task_id,  -- Explicit cast to UUID
        tb.instruction,
        tb.task_type,
        tb.order_in_section,
        tb.created_at
    FROM task_base tb
    WHERE tb.section_id = p_section_id
    ORDER BY tb.order_in_section;
END;
$$;

-- 5. Fix get_mastery_tasks_for_course - use task_id from student_mastery_progress
DROP FUNCTION IF EXISTS public.get_mastery_tasks_for_course(TEXT, UUID);

CREATE FUNCTION public.get_mastery_tasks_for_course(
    p_session_id TEXT,
    p_course_id UUID
)
RETURNS TABLE (
    task_id UUID,
    task_title TEXT,
    task_type TEXT,
    unit_id UUID,
    unit_title TEXT,
    section_id UUID,
    section_title TEXT,
    review_after TIMESTAMP WITH TIME ZONE,
    proficiency_score NUMERIC
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
    
    -- Check if user is enrolled in course or is the teacher
    IF v_user_role = 'student' THEN
        IF NOT EXISTS (
            SELECT 1 FROM course_student 
            WHERE course_id = p_course_id AND student_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Student not enrolled in course';
        END IF;
    ELSIF v_user_role = 'teacher' THEN
        IF NOT EXISTS (
            SELECT 1 FROM course 
            WHERE id = p_course_id AND creator_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Teacher does not own this course';
        END IF;
    END IF;
    
    -- Get all mastery tasks for the course with proper joins
    RETURN QUERY
    SELECT DISTINCT
        tb.id as task_id,
        tb.instruction as task_title,
        tb.task_type,
        lu.id as unit_id,
        lu.title as unit_title,
        us.id as section_id,
        us.title as section_title,
        smp.last_reviewed_at + (smp.next_due_date - CURRENT_DATE)::interval as review_after,
        smp.difficulty::NUMERIC as proficiency_score
    FROM task_base tb
    JOIN unit_section us ON us.id = tb.section_id
    JOIN learning_unit lu ON lu.id = us.unit_id
    JOIN course_learning_unit_assignment cla ON cla.unit_id = lu.id
    LEFT JOIN student_mastery_progress smp ON 
        smp.student_id = v_user_id AND
        smp.task_id = tb.id  -- Join on task_id, not unit_id
    WHERE cla.course_id = p_course_id 
        AND tb.task_type = 'mastery_task'
    ORDER BY lu.title, us.order_in_unit, tb.order_in_section;
END;
$$;

-- Grant necessary permissions
GRANT EXECUTE ON FUNCTION public._get_submission_status_matrix_uncached(TEXT, UUID, UUID) TO anon;
GRANT EXECUTE ON FUNCTION public.get_submissions_for_course_and_unit(TEXT, UUID, UUID) TO anon;
GRANT EXECUTE ON FUNCTION public.get_published_section_details_for_student(TEXT, UUID, UUID, UUID) TO anon;
GRANT EXECUTE ON FUNCTION public.get_section_tasks(TEXT, UUID) TO anon;
GRANT EXECUTE ON FUNCTION public.get_mastery_tasks_for_course(TEXT, UUID) TO anon;