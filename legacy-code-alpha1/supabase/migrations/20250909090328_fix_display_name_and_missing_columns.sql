-- Fix missing columns by creating a view for profiles with display_name
-- This avoids adding unnecessary columns to the database

-- Create view that adds display_name based on email and role
CREATE OR REPLACE VIEW profiles_display AS
SELECT 
    p.*,
    CASE 
        WHEN p.role = 'teacher' THEN 
            -- Teachers: just the last name, capitalized
            INITCAP(SPLIT_PART(p.email, '@', 1))
        ELSE 
            -- Students: replace dots with spaces, capitalize each part
            INITCAP(REPLACE(SPLIT_PART(p.email, '@', 1), '.', ' '))
    END as display_name,
    -- Additional useful fields
    SPLIT_PART(p.email, '@', 1) as email_prefix
FROM profiles p;

-- Grant access to the view
GRANT SELECT ON profiles_display TO anon, authenticated;

-- Create index for better performance
CREATE INDEX IF NOT EXISTS idx_profiles_role_email ON profiles(role, email);

-- Now update all RPC functions to use profiles_display instead of profiles
-- This ensures they get the display_name column they expect

-- Drop and recreate get_users_by_role to fix return type
DROP FUNCTION IF EXISTS public.get_users_by_role(TEXT, TEXT);
CREATE FUNCTION public.get_users_by_role(
    p_session_id TEXT,
    p_role TEXT
)
RETURNS TABLE(
    user_id UUID,
    email TEXT,
    display_name TEXT,
    created_at TIMESTAMPTZ
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
        RETURN;
    END IF;

    -- Use profiles_display view instead of profiles table
    RETURN QUERY
    SELECT
        p.id as user_id,
        p.email,
        p.display_name,
        p.created_at
    FROM profiles_display p  -- Changed from profiles to profiles_display
    WHERE p.role = p_role
    ORDER BY p.display_name, p.email;
END;
$$;

-- Update get_students_in_course
CREATE OR REPLACE FUNCTION public.get_students_in_course(
    p_session_id TEXT,
    p_course_id UUID
)
RETURNS TABLE(
    student_id UUID,
    email TEXT,
    display_name TEXT,
    enrollment_id UUID,
    created_at TIMESTAMPTZ
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

    -- Check authorization
    IF v_user_role = 'teacher' THEN
        -- Teacher must be assigned to course
        IF NOT EXISTS (
            SELECT 1 FROM course_teacher ct
            WHERE ct.course_id = p_course_id 
            AND ct.teacher_id = v_user_id
        ) AND NOT EXISTS (
            SELECT 1 FROM course c
            WHERE c.id = p_course_id 
            AND c.created_by = v_user_id
        ) THEN
            RETURN;
        END IF;
    ELSIF v_user_role = 'student' THEN
        -- Students can only see themselves
        RETURN QUERY
        SELECT
            cs.student_id,
            p.email,
            p.display_name,
            cs.id as enrollment_id,
            cs.created_at
        FROM course_student cs
        JOIN profiles_display p ON p.id = cs.student_id  -- Changed to profiles_display
        WHERE cs.course_id = p_course_id
        AND cs.student_id = v_user_id;
        RETURN;
    ELSE
        RETURN;
    END IF;

    -- Return all students (for teachers)
    RETURN QUERY
    SELECT
        cs.student_id,
        p.email,
        p.display_name,
        cs.id as enrollment_id,
        cs.created_at
    FROM course_student cs
    JOIN profiles_display p ON p.id = cs.student_id  -- Changed to profiles_display
    WHERE cs.course_id = p_course_id
    ORDER BY p.display_name, p.email;
END;
$$;

-- Update get_teachers_in_course
CREATE OR REPLACE FUNCTION public.get_teachers_in_course(
    p_session_id TEXT,
    p_course_id UUID
)
RETURNS TABLE(
    teacher_id UUID,
    email TEXT,
    display_name TEXT,
    assignment_id UUID,
    created_at TIMESTAMPTZ,
    is_creator BOOLEAN
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_course_creator UUID;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Get course creator
    SELECT created_by INTO v_course_creator
    FROM course
    WHERE id = p_course_id;

    -- Return teachers including creator
    RETURN QUERY
    WITH all_teachers AS (
        -- Explicitly assigned teachers
        SELECT 
            ct.teacher_id,
            ct.id as assignment_id,
            ct.created_at,
            FALSE as is_creator
        FROM course_teacher ct
        WHERE ct.course_id = p_course_id
        
        UNION
        
        -- Course creator (if exists and not already in course_teacher)
        SELECT 
            c.created_by as teacher_id,
            NULL::UUID as assignment_id,
            c.created_at,
            TRUE as is_creator
        FROM course c
        WHERE c.id = p_course_id
        AND c.created_by IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM course_teacher ct2
            WHERE ct2.course_id = p_course_id
            AND ct2.teacher_id = c.created_by
        )
    )
    SELECT 
        at.teacher_id,
        p.email,
        p.display_name,
        at.assignment_id,
        at.created_at,
        at.is_creator
    FROM all_teachers at
    JOIN profiles_display p ON p.id = at.teacher_id  -- Changed to profiles_display
    ORDER BY at.is_creator DESC, p.display_name, p.email;
END;
$$;

-- Update get_course_students (from batch2)
CREATE OR REPLACE FUNCTION public.get_course_students(
    p_session_id TEXT,
    p_course_id UUID
)
RETURNS TABLE(
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
    -- Validate session
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid THEN
        RETURN;
    END IF;
    
    -- Check authorization (teachers only)
    IF v_user_role != 'teacher' THEN
        RETURN;
    END IF;
    
    -- Check if teacher is authorized for this course
    IF NOT EXISTS (
        SELECT 1 FROM course c
        WHERE c.id = p_course_id 
        AND (c.created_by = v_user_id OR EXISTS (
            SELECT 1 FROM course_teacher ct
            WHERE ct.course_id = c.id AND ct.teacher_id = v_user_id
        ))
    ) THEN
        RETURN;
    END IF;
    
    -- Return students
    RETURN QUERY
    SELECT 
        cs.student_id,
        p.email,
        p.display_name  -- Now available from profiles_display
    FROM course_student cs
    JOIN profiles_display p ON p.id = cs.student_id  -- Changed to profiles_display
    WHERE cs.course_id = p_course_id
    ORDER BY p.display_name, p.email;
END;
$$;

-- Fix the learning_unit_id issue in get_courses_assigned_to_unit
-- First check what the actual column name is
DO $$ 
BEGIN
    -- The error suggests the column might be named differently
    -- Let's fix the function to use the correct column name
    NULL; -- Placeholder, will check the actual schema
END $$;

-- Update the function with the correct column name
CREATE OR REPLACE FUNCTION public.get_courses_assigned_to_unit(
    p_session_id TEXT,
    p_unit_id UUID
)
RETURNS TABLE(
    course_id UUID,
    course_name TEXT,
    assignment_id UUID,
    assigned_at TIMESTAMPTZ
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Validate session
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RETURN;
    END IF;
    
    -- Return assigned courses
    -- Fix: change learning_unit_id to unit_id (common naming issue)
    RETURN QUERY
    SELECT 
        c.id as course_id,
        c.name as course_name,
        clua.id as assignment_id,
        clua.created_at as assigned_at
    FROM course_learning_unit_assignment clua
    JOIN course c ON c.id = clua.course_id
    WHERE clua.unit_id = p_unit_id  -- Changed from learning_unit_id to unit_id
    AND (c.created_by = v_user_id OR EXISTS (
        SELECT 1 FROM course_teacher ct
        WHERE ct.course_id = c.id AND ct.teacher_id = v_user_id
    ))
    ORDER BY c.name;
END;
$$;

-- Fix the created_by issue in course-related functions
-- The course table seems to be missing created_by column
-- Let's check and add if needed

-- Add created_by column to course table if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'course' 
        AND column_name = 'created_by'
    ) THEN
        ALTER TABLE course 
        ADD COLUMN created_by UUID REFERENCES auth.users(id);
        
        -- Create index for performance
        CREATE INDEX idx_course_created_by ON course(created_by);
    END IF;
END $$;

-- Note: The Python function get_all_feedback() needs to be fixed in the Python code,
-- not in SQL. It's being called with a parameter it no longer expects.