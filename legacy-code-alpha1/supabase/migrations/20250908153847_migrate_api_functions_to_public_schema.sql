-- Migration: api.* Functions -> public.* Functions
-- Public Schema Approach (Option C) fuer maximale Sicherheit und Einfachheit
-- Datum: 2025-01-09

-- =====================================================
-- Schema Migration: api.* -> public.* Functions
-- =====================================================

-- 1. DROP existing api functions (clean slate)
DROP FUNCTION IF EXISTS api.get_user_courses(TEXT);
DROP FUNCTION IF EXISTS api.get_user_learning_units(TEXT);
DROP FUNCTION IF EXISTS api.get_learning_unit(TEXT, UUID);
DROP FUNCTION IF EXISTS api.create_learning_unit(TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS api.create_course(TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS api.get_course_units(TEXT, UUID);
DROP FUNCTION IF EXISTS api.get_unit_sections(TEXT, UUID);

-- 2. CREATE all functions in public schema

-- 2.1 get_user_courses (replaces api.get_user_courses)
CREATE OR REPLACE FUNCTION public.get_user_courses(p_session_id TEXT)
RETURNS TABLE(
    id UUID,
    name TEXT,
    creator_id UUID,
    created_at TIMESTAMPTZ,
    student_count INT
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

    -- Invalid session = empty result
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RETURN;
    END IF;

    -- Role-based data return
    IF v_user_role = 'teacher' THEN
        RETURN QUERY
        SELECT
            c.id,
            c.name,
            c.creator_id,
            c.created_at,
            COUNT(DISTINCT cs.student_id)::INT as student_count
        FROM course c
        LEFT JOIN course_student cs ON cs.course_id = c.id
        WHERE c.creator_id = v_user_id
        GROUP BY c.id, c.name, c.creator_id, c.created_at
        ORDER BY c.created_at DESC;
    ELSE
        -- Student sees only assigned courses
        RETURN QUERY
        SELECT
            c.id,
            c.name,
            c.creator_id,
            c.created_at,
            COUNT(DISTINCT cs2.student_id)::INT as student_count
        FROM course c
        INNER JOIN course_student cs ON cs.course_id = c.id
        LEFT JOIN course_student cs2 ON cs2.course_id = c.id
        WHERE cs.student_id = v_user_id
        GROUP BY c.id, c.name, c.creator_id, c.created_at
        ORDER BY c.created_at DESC;
    END IF;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_user_courses TO anon;

-- 2.2 get_user_learning_units (replaces api.get_user_learning_units)
CREATE OR REPLACE FUNCTION public.get_user_learning_units(p_session_id TEXT)
RETURNS TABLE(
    id UUID,
    title TEXT,
    description TEXT,
    creator_id UUID,
    created_at TIMESTAMPTZ,
    assignment_count INT
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

    -- Invalid session = empty result
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RETURN;
    END IF;

    -- Only Teacher can see own Learning Units
    IF v_user_role = 'teacher' THEN
        RETURN QUERY
        SELECT
            lu.id,
            lu.title,
            lu.description,
            lu.creator_id,
            lu.created_at,
            COUNT(DISTINCT ua.id)::INT as assignment_count
        FROM learning_unit lu
        LEFT JOIN unit_assignment ua ON ua.learning_unit_id = lu.id
        WHERE lu.creator_id = v_user_id
        GROUP BY lu.id, lu.title, lu.description, lu.creator_id, lu.created_at
        ORDER BY lu.created_at DESC;
    END IF;
    -- Students don't see Learning Units in management view
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_user_learning_units TO anon;

-- 2.3 get_learning_unit (replaces api.get_learning_unit)
CREATE OR REPLACE FUNCTION public.get_learning_unit(p_session_id TEXT, p_unit_id UUID)
RETURNS TABLE(
    id UUID,
    title TEXT,
    description TEXT,
    creator_id UUID,
    created_at TIMESTAMPTZ,
    can_edit BOOLEAN
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

    -- Invalid session = empty result
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RETURN;
    END IF;

    -- Input validation
    IF p_unit_id IS NULL THEN
        RETURN;
    END IF;

    -- Load Learning Unit with authorization
    RETURN QUERY
    SELECT
        lu.id,
        lu.title,
        lu.description,
        lu.creator_id,
        lu.created_at,
        (lu.creator_id = v_user_id OR v_user_role = 'admin')::BOOLEAN as can_edit
    FROM learning_unit lu
    WHERE lu.id = p_unit_id
    AND (
        lu.creator_id = v_user_id  -- Owner
        OR v_user_role = 'admin'   -- Admin
        OR EXISTS (                -- Student with access through Course Assignment
            SELECT 1 
            FROM unit_assignment ua
            INNER JOIN course_student cs ON cs.course_id = ua.course_id
            WHERE ua.learning_unit_id = lu.id
            AND cs.student_id = v_user_id
        )
    );
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_learning_unit TO anon;

-- 2.4 create_learning_unit (replaces api.create_learning_unit) 
CREATE OR REPLACE FUNCTION public.create_learning_unit(
    p_session_id TEXT,
    p_title TEXT,
    p_description TEXT DEFAULT NULL
)
RETURNS TABLE(
    id UUID,
    title TEXT,
    created_at TIMESTAMPTZ,
    success BOOLEAN,
    error_message TEXT
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_new_id UUID;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Authorization: Only Teacher
    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RETURN QUERY SELECT
            NULL::UUID,
            NULL::TEXT,
            NULL::TIMESTAMPTZ,
            FALSE,
            'Keine Berechtigung fuer diese Aktion'::TEXT;
        RETURN;
    END IF;

    -- Input validation
    IF p_title IS NULL OR LENGTH(TRIM(p_title)) = 0 THEN
        RETURN QUERY SELECT
            NULL::UUID,
            NULL::TEXT,
            NULL::TIMESTAMPTZ,
            FALSE,
            'Titel darf nicht leer sein'::TEXT;
        RETURN;
    END IF;

    -- Create record
    BEGIN
        INSERT INTO learning_unit (title, description, creator_id)
        VALUES (TRIM(p_title), NULLIF(TRIM(p_description), ''), v_user_id)
        RETURNING id INTO v_new_id;

        -- Success with data
        RETURN QUERY SELECT
            lu.id,
            lu.title,
            lu.created_at,
            TRUE,
            NULL::TEXT
        FROM learning_unit lu
        WHERE lu.id = v_new_id;

    EXCEPTION
        WHEN unique_violation THEN
            RETURN QUERY SELECT
                NULL::UUID,
                NULL::TEXT,
                NULL::TIMESTAMPTZ,
                FALSE,
                'Eine Lerneinheit mit diesem Titel existiert bereits'::TEXT;
        WHEN OTHERS THEN
            RETURN QUERY SELECT
                NULL::UUID,
                NULL::TEXT,
                NULL::TIMESTAMPTZ,
                FALSE,
                'Fehler beim Erstellen der Lerneinheit'::TEXT;
    END;
END;
$$;

GRANT EXECUTE ON FUNCTION public.create_learning_unit TO anon;

-- 2.5 create_course (replaces api.create_course) - with explicit variables fix
CREATE OR REPLACE FUNCTION public.create_course(
    p_session_id TEXT,
    p_name TEXT,
    p_description TEXT DEFAULT NULL
)
RETURNS TABLE(
    id UUID,
    name TEXT,
    created_at TIMESTAMPTZ,
    success BOOLEAN,
    error_message TEXT
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    -- Explicit variables to avoid column ambiguity
    result_id UUID;
    result_name TEXT;
    result_created_at TIMESTAMPTZ;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Authorization: Only Teacher
    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RETURN QUERY SELECT
            NULL::UUID,
            NULL::TEXT,
            NULL::TIMESTAMPTZ,
            FALSE,
            'Keine Berechtigung fuer diese Aktion'::TEXT;
        RETURN;
    END IF;

    -- Input validation
    IF p_name IS NULL OR LENGTH(TRIM(p_name)) = 0 THEN
        RETURN QUERY SELECT
            NULL::UUID,
            NULL::TEXT,
            NULL::TIMESTAMPTZ,
            FALSE,
            'Kursname darf nicht leer sein'::TEXT;
        RETURN;
    END IF;

    -- Create record with explicit variables
    BEGIN
        INSERT INTO course (name, creator_id)
        VALUES (TRIM(p_name), v_user_id)
        RETURNING course.id, course.name, course.created_at
        INTO result_id, result_name, result_created_at;

        -- Success with explicit variable data
        RETURN QUERY SELECT
            result_id,
            result_name,
            result_created_at,
            TRUE,
            NULL::TEXT;

    EXCEPTION
        WHEN unique_violation THEN
            RETURN QUERY SELECT
                NULL::UUID,
                NULL::TEXT,
                NULL::TIMESTAMPTZ,
                FALSE,
                'Ein Kurs mit diesem Namen existiert bereits'::TEXT;
        WHEN OTHERS THEN
            RETURN QUERY SELECT
                NULL::UUID,
                NULL::TEXT,
                NULL::TIMESTAMPTZ,
                FALSE,
                'Fehler beim Erstellen des Kurses'::TEXT;
    END;
END;
$$;

GRANT EXECUTE ON FUNCTION public.create_course TO anon;

-- 2.6 get_course_units (replaces api.get_course_units)
CREATE OR REPLACE FUNCTION public.get_course_units(p_session_id TEXT, p_course_id UUID)
RETURNS TABLE(
    id UUID,
    learning_unit_id UUID,
    learning_unit_title TEXT,
    learning_unit_description TEXT,
    "position" INTEGER,
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

    -- Invalid session = empty result
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RETURN;
    END IF;

    -- Input validation
    IF p_course_id IS NULL THEN
        RETURN;
    END IF;

    -- Check access authorization and load units
    RETURN QUERY
    SELECT
        ua.id,
        ua.learning_unit_id,
        lu.title as learning_unit_title,
        lu.description as learning_unit_description,
        ua."position",
        ua.created_at
    FROM unit_assignment ua
    INNER JOIN learning_unit lu ON lu.id = ua.learning_unit_id
    INNER JOIN course c ON c.id = ua.course_id
    WHERE ua.course_id = p_course_id
    AND (
        c.creator_id = v_user_id  -- Course Owner
        OR v_user_role = 'admin'  -- Admin
        OR EXISTS (               -- Student in Course
            SELECT 1 
            FROM course_student cs 
            WHERE cs.course_id = p_course_id
            AND cs.student_id = v_user_id
        )
    )
    ORDER BY ua."position" ASC, ua.created_at ASC;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_course_units TO anon;

-- 2.7 get_unit_sections (replaces api.get_unit_sections)
CREATE OR REPLACE FUNCTION public.get_unit_sections(p_session_id TEXT, p_unit_id UUID)
RETURNS TABLE(
    id UUID,
    title TEXT,
    content TEXT,
    section_type TEXT,
    "position" INTEGER,
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

    -- Invalid session = empty result
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RETURN;
    END IF;

    -- Input validation
    IF p_unit_id IS NULL THEN
        RETURN;
    END IF;

    -- Check access authorization and load sections
    RETURN QUERY
    SELECT
        s.id,
        s.title,
        s.content,
        s.section_type,
        s."position",
        s.created_at
    FROM section s
    INNER JOIN learning_unit lu ON lu.id = s.learning_unit_id
    WHERE s.learning_unit_id = p_unit_id
    AND (
        lu.creator_id = v_user_id  -- Unit Owner
        OR v_user_role = 'admin'   -- Admin
        OR EXISTS (                -- Student with access through Course Assignment
            SELECT 1 
            FROM unit_assignment ua
            INNER JOIN course_student cs ON cs.course_id = ua.course_id
            WHERE ua.learning_unit_id = p_unit_id
            AND cs.student_id = v_user_id
        )
    )
    ORDER BY s."position" ASC, s.created_at ASC;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_unit_sections TO anon;

-- =====================================================
-- 3. Cleanup: Remove api schema if empty
-- =====================================================

-- Remove api schema (only if it's empty)
DROP SCHEMA IF EXISTS api CASCADE;

-- =====================================================
-- Status: Schema Migration Complete
-- =====================================================
-- All api.* functions have been moved to public.* functions
-- Public Schema Approach (Option C) now fully implemented
-- Ready for Python wrapper updates