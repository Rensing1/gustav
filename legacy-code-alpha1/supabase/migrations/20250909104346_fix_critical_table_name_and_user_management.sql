-- Fix critical table name and user management issues
-- Problem 1: section_course_publication -> course_unit_section_status table name fix
-- Problem 2: add/remove_user_to_course improved validation and error handling

BEGIN;

-- =============================================================================
-- 1. Fix get_section_statuses_for_unit_in_course: Use correct table name
-- =============================================================================

CREATE OR REPLACE FUNCTION public.get_section_statuses_for_unit_in_course(
    p_session_id TEXT,
    p_unit_id UUID,
    p_course_id UUID
)
RETURNS TABLE(
    section_id uuid,
    is_published boolean
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

    -- Authorization check (teachers only for this function)
    IF v_user_role != 'teacher' THEN
        RETURN;
    END IF;
    
    -- Check if teacher is authorized for this course  
    IF NOT EXISTS (
        SELECT 1 FROM course c 
        WHERE c.id = p_course_id 
        AND (c.creator_id = v_user_id OR EXISTS (
            SELECT 1 FROM course_teacher ct 
            WHERE ct.course_id = p_course_id 
            AND ct.teacher_id = v_user_id
        ))
    ) THEN
        RETURN;
    END IF;

    -- Return section publication status using CORRECT table name: course_unit_section_status
    RETURN QUERY
    SELECT 
        us.id as section_id,
        COALESCE(cuss.is_published, FALSE) as is_published
    FROM unit_section us
    LEFT JOIN course_unit_section_status cuss ON cuss.section_id = us.id AND cuss.course_id = p_course_id
    WHERE us.unit_id = p_unit_id
    ORDER BY us.order_in_unit;
END;
$$;

-- =============================================================================
-- 2. Fix add_user_to_course: Better error handling and validation
-- =============================================================================

CREATE OR REPLACE FUNCTION public.add_user_to_course(
    p_session_id TEXT,
    p_user_id UUID,
    p_course_id UUID,
    p_role TEXT
)
RETURNS VOID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_target_user_exists BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Only teachers can add users to courses
    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized access' USING ERRCODE = '42501';
    END IF;

    -- Validate role parameter
    IF p_role NOT IN ('student', 'teacher') THEN
        RAISE EXCEPTION 'Invalid role parameter' USING ERRCODE = '22023';
    END IF;
    
    -- Check if target user exists
    SELECT EXISTS (SELECT 1 FROM profiles WHERE id = p_user_id) INTO v_target_user_exists;
    IF NOT v_target_user_exists THEN
        RAISE EXCEPTION 'User not found' USING ERRCODE = '22023';
    END IF;

    -- Check if teacher is authorized for this course
    IF NOT EXISTS (
        SELECT 1 FROM course c 
        WHERE c.id = p_course_id 
        AND (c.creator_id = v_user_id OR EXISTS (
            SELECT 1 FROM course_teacher ct 
            WHERE ct.course_id = p_course_id 
            AND ct.teacher_id = v_user_id
        ))
    ) THEN
        RAISE EXCEPTION 'Course access denied' USING ERRCODE = '42501';
    END IF;

    -- Add user to appropriate table based on role
    IF p_role = 'student' THEN
        -- Insert into course_student, ignore if already exists
        INSERT INTO course_student (course_id, student_id)
        VALUES (p_course_id, p_user_id)
        ON CONFLICT (course_id, student_id) DO NOTHING;
    ELSIF p_role = 'teacher' THEN
        -- Insert into course_teacher, ignore if already exists
        INSERT INTO course_teacher (course_id, teacher_id)
        VALUES (p_course_id, p_user_id)
        ON CONFLICT (course_id, teacher_id) DO NOTHING;
    END IF;
END;
$$;

-- =============================================================================
-- 3. Fix remove_user_from_course: Better error handling and validation
-- =============================================================================

CREATE OR REPLACE FUNCTION public.remove_user_from_course(
    p_session_id TEXT,
    p_user_id UUID,
    p_course_id UUID,
    p_role TEXT
)
RETURNS VOID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_teacher_count INTEGER;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Only teachers can remove users from courses
    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized access' USING ERRCODE = '42501';
    END IF;

    -- Validate role parameter
    IF p_role NOT IN ('student', 'teacher') THEN
        RAISE EXCEPTION 'Invalid role parameter' USING ERRCODE = '22023';
    END IF;

    -- Check if teacher is authorized for this course
    IF NOT EXISTS (
        SELECT 1 FROM course c 
        WHERE c.id = p_course_id 
        AND (c.creator_id = v_user_id OR EXISTS (
            SELECT 1 FROM course_teacher ct 
            WHERE ct.course_id = p_course_id 
            AND ct.teacher_id = v_user_id
        ))
    ) THEN
        RAISE EXCEPTION 'Course access denied' USING ERRCODE = '42501';
    END IF;

    -- Special handling for teacher removal
    IF p_role = 'teacher' THEN
        -- Count total teachers (including course creator)
        SELECT COUNT(*) INTO v_teacher_count
        FROM (
            SELECT teacher_id FROM course_teacher WHERE course_id = p_course_id
            UNION
            SELECT creator_id FROM course WHERE id = p_course_id
        ) t;
        
        -- Prevent removing if it would leave course without teachers
        IF v_teacher_count <= 1 THEN
            RAISE EXCEPTION 'Cannot remove last teacher' USING ERRCODE = '23514';
        END IF;
    END IF;

    -- Remove user from appropriate table based on role
    IF p_role = 'student' THEN
        DELETE FROM course_student 
        WHERE course_id = p_course_id AND student_id = p_user_id;
    ELSIF p_role = 'teacher' THEN
        DELETE FROM course_teacher 
        WHERE course_id = p_course_id AND teacher_id = p_user_id;
    END IF;
END;
$$;

COMMIT;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION public.get_section_statuses_for_unit_in_course TO anon;
GRANT EXECUTE ON FUNCTION public.add_user_to_course TO anon;
GRANT EXECUTE ON FUNCTION public.remove_user_from_course TO anon;