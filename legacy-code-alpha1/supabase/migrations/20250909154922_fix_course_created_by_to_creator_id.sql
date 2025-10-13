-- Fix: Update all functions to use 'creator_id' instead of 'created_by' for course table

-- 1. add_user_to_course - Fix line 35
DROP FUNCTION IF EXISTS public.add_user_to_course(TEXT, UUID, UUID, TEXT);
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
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can add users to courses';
    END IF;

    -- Check if teacher is authorized for this course
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id  -- Fixed: changed created_by to creator_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Dynamic table selection based on role
    IF p_role = 'student' THEN
        INSERT INTO course_student (student_id, course_id)
        VALUES (p_user_id, p_course_id)
        ON CONFLICT (student_id, course_id) DO NOTHING;
    ELSIF p_role = 'teacher' THEN
        INSERT INTO course_teacher (teacher_id, course_id)
        VALUES (p_user_id, p_course_id)
        ON CONFLICT (teacher_id, course_id) DO NOTHING;
    ELSE
        RAISE EXCEPTION 'Invalid role: %', p_role;
    END IF;
END;
$$;

GRANT EXECUTE ON FUNCTION public.add_user_to_course TO anon;

-- 2. remove_user_from_course - Fix lines 89 and 101
DROP FUNCTION IF EXISTS public.remove_user_from_course(TEXT, UUID, UUID, TEXT);
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
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can remove users from courses';
    END IF;

    -- Check if teacher is authorized for this course
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id  -- Fixed: changed created_by to creator_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Dynamic table selection based on role
    IF p_role = 'student' THEN
        DELETE FROM course_student 
        WHERE student_id = p_user_id AND course_id = p_course_id;
    ELSIF p_role = 'teacher' THEN
        -- Prevent removing course creator
        IF EXISTS (
            SELECT 1 FROM course 
            WHERE id = p_course_id AND creator_id = p_user_id  -- Fixed: changed created_by to creator_id
        ) THEN
            RAISE EXCEPTION 'Cannot remove course creator';
        END IF;
        
        DELETE FROM course_teacher 
        WHERE teacher_id = p_user_id AND course_id = p_course_id;
    ELSE
        RAISE EXCEPTION 'Invalid role: %', p_role;
    END IF;
END;
$$;

GRANT EXECUTE ON FUNCTION public.remove_user_from_course TO anon;

-- 3. assign_unit_to_course - Fix line 147
DROP FUNCTION IF EXISTS public.assign_unit_to_course(TEXT, UUID, UUID);
CREATE OR REPLACE FUNCTION public.assign_unit_to_course(
    p_session_id TEXT,
    p_unit_id UUID,
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
    v_order_in_course INT;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can assign units to courses';
    END IF;

    -- Check if teacher is authorized for this course
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id  -- Fixed: changed created_by to creator_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Get next order position
    SELECT COALESCE(MAX(order_in_course), 0) + 1
    INTO v_order_in_course
    FROM course_learning_unit_assignment
    WHERE course_id = p_course_id;

    -- Insert assignment
    INSERT INTO course_learning_unit_assignment (
        learning_unit_id, 
        course_id, 
        order_in_course
    )
    VALUES (p_unit_id, p_course_id, v_order_in_course)
    ON CONFLICT (learning_unit_id, course_id) DO NOTHING;
END;
$$;

GRANT EXECUTE ON FUNCTION public.assign_unit_to_course TO anon;

-- 4. unassign_unit_from_course - Fix line 201
DROP FUNCTION IF EXISTS public.unassign_unit_from_course(TEXT, UUID, UUID);
CREATE OR REPLACE FUNCTION public.unassign_unit_from_course(
    p_session_id TEXT,
    p_unit_id UUID,
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
        RAISE EXCEPTION 'Unauthorized: Only teachers can unassign units from courses';
    END IF;

    -- Check if teacher is authorized for this course
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id  -- Fixed: changed created_by to creator_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Delete assignment
    DELETE FROM course_learning_unit_assignment
    WHERE learning_unit_id = p_unit_id AND course_id = p_course_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.unassign_unit_from_course TO anon;

-- 5. update_course - Fix line 244
DROP FUNCTION IF EXISTS public.update_course(TEXT, UUID, TEXT);
CREATE OR REPLACE FUNCTION public.update_course(
    p_session_id TEXT,
    p_course_id UUID,
    p_name TEXT
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
        RAISE EXCEPTION 'Unauthorized: Only teachers can update courses';
    END IF;

    -- Check if teacher is authorized for this course
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id  -- Fixed: changed created_by to creator_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Update course
    UPDATE course
    SET name = p_name,
        updated_at = NOW()
    WHERE id = p_course_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.update_course TO anon;

-- 6. delete_course - Fix line 285
DROP FUNCTION IF EXISTS public.delete_course(TEXT, UUID);
CREATE OR REPLACE FUNCTION public.delete_course(
    p_session_id TEXT,
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
        RAISE EXCEPTION 'Unauthorized: Only teachers can delete courses';
    END IF;

    -- Check if teacher is course creator
    IF NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id  -- Fixed: changed created_by to creator_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Only course creator can delete the course';
    END IF;

    -- Delete course (CASCADE will handle related records)
    DELETE FROM course
    WHERE id = p_course_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.delete_course TO anon;

-- 7. is_teacher_authorized_for_course - Fix line 327
DROP FUNCTION IF EXISTS public.is_teacher_authorized_for_course(TEXT, UUID);
CREATE OR REPLACE FUNCTION public.is_teacher_authorized_for_course(
    p_session_id TEXT,
    p_course_id UUID
)
RETURNS BOOLEAN
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
        RETURN FALSE;
    END IF;

    -- Check authorization
    RETURN EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) OR EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id  -- Fixed: changed created_by to creator_id
    );
END;
$$;

GRANT EXECUTE ON FUNCTION public.is_teacher_authorized_for_course TO anon;

-- 8. get_course_students - Fix line 367
DROP FUNCTION IF EXISTS public.get_course_students(TEXT, UUID);
CREATE OR REPLACE FUNCTION public.get_course_students(
    p_session_id TEXT,
    p_course_id UUID
)
RETURNS TABLE (
    student_id UUID,
    email TEXT,
    display_name TEXT
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
        RAISE EXCEPTION 'Unauthorized: Only teachers can view course students';
    END IF;

    -- Check if teacher is authorized for this course
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id  -- Fixed: changed created_by to creator_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Return students
    RETURN QUERY
    SELECT 
        cs.student_id,
        p.email,
        COALESCE(p.display_name, SPLIT_PART(p.email, '@', 1)) as display_name
    FROM course_student cs
    JOIN profiles p ON p.id = cs.student_id
    WHERE cs.course_id = p_course_id
    ORDER BY p.email;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_course_students TO anon;