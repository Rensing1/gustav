-- Fix multiple column reference issues in various functions

-- 1. Fix get_published_section_details_for_student
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
            SELECT 1 FROM course -- Changed from courses to course
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
        WHERE s.unit_id = p_unit_id -- Changed from learning_unit_id to unit_id
    ),
    task_details AS (
        -- Get regular tasks with submission info
        SELECT 
            t.section_id,
            jsonb_build_object(
                'id', t.id,
                'title', t.instruction,  -- Use instruction instead of title
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
                            'submitted_at', MAX(sub.timestamp),
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
        GROUP BY t.id, t.section_id, t.instruction, t.task_type, t.order_in_section, t.max_attempts, t.prompt
        
        UNION ALL
        
        -- Get mastery tasks with submission info
        SELECT 
            m.section_id,
            jsonb_build_object(
                'id', m.id,
                'title', m.instruction,  -- Use instruction instead of title
                'task_type', m.task_type,
                'order_in_section', m.order_in_section,
                'is_mastery', TRUE,
                'max_attempts', NULL,
                'prompt', m.prompt,
                'submission_count', COUNT(sub.id),
                'attempts_remaining', NULL,
                'latest_submission', 
                CASE 
                    WHEN COUNT(sub.id) > 0 THEN
                        jsonb_build_object(
                            'id', MAX(sub.id),
                            'is_correct', BOOL_OR(sub.is_correct),
                            'submitted_at', MAX(sub.timestamp),
                            'has_feedback', MAX(sub.ai_feedback) IS NOT NULL OR MAX(sub.teacher_feedback) IS NOT NULL,
                            'feedback_viewed', MAX(sub.feedback_viewed_at) IS NOT NULL
                        )
                    ELSE NULL
                END
            ) as task_data
        FROM all_mastery_tasks m
        LEFT JOIN submission sub ON 
            sub.task_id = m.id AND 
            sub.student_id = p_student_id
        GROUP BY m.id, m.section_id, m.instruction, m.task_type, m.order_in_section, m.prompt
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
    WHERE ps.is_published = TRUE
    GROUP BY ps.id, ps.title, ps.description, ps.materials, ps.order_in_unit, ps.is_published
    ORDER BY ps.order_in_unit;
END;
$$;

-- 2. Fix get_submissions_for_course_and_unit - change t.title to s.title
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
            COALESCE(p.display_name, u.email::text) as student_name
        FROM course_student cs
        JOIN auth.users u ON u.id = cs.student_id
        LEFT JOIN profiles p ON p.id = cs.student_id
        WHERE cs.course_id = p_course_id
    ),
    unit_tasks AS (
        SELECT 
            tb.id as task_id,
            tb.instruction as task_title, -- Changed from title to instruction
            tb.task_type,
            tb.section_id,
            s.title as section_title -- Use s.title for section
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
        sub.timestamp as submitted_at,
        sub.ai_feedback,
        sub.teacher_feedback,
        sub.teacher_override
    FROM course_students cs
    CROSS JOIN unit_tasks ut
    LEFT JOIN submission sub ON 
        sub.student_id = cs.student_id AND 
        sub.task_id = ut.task_id
    ORDER BY cs.student_name, ut.section_id, ut.task_id, sub.timestamp DESC;
END;
$$;

-- 3. Fix get_mastery_tasks_for_course - fix tb.title reference
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
    
    -- Get all mastery tasks for the course
    RETURN QUERY
    SELECT DISTINCT
        tb.id as task_id,
        tb.instruction as task_title, -- Changed from tb.title to tb.instruction
        tb.task_type,
        lu.id as unit_id,
        lu.title as unit_title,
        us.id as section_id,
        us.title as section_title,
        mts.review_after,
        mts.proficiency_score
    FROM task_base tb
    JOIN unit_section us ON us.id = tb.section_id
    JOIN learning_unit lu ON lu.id = us.unit_id
    JOIN course_learning_unit_assignment cla ON cla.unit_id = lu.id
    LEFT JOIN mastery_task_state mts ON 
        mts.task_id = tb.id AND 
        mts.student_id = v_user_id
    WHERE cla.course_id = p_course_id 
        AND tb.task_type = 'mastery_task'
    ORDER BY lu.title, us.order_in_unit, tb.order_in_section;
END;
$$;