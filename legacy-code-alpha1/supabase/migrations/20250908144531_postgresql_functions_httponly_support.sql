-- PostgreSQL Functions Migration for HttpOnly Cookie Support
-- Migration: 20250908144531_postgresql_functions_httponly_support.sql
-- Datum: 2025-01-09
-- Zweck: Session-based PostgreSQL Functions for all 59 DB-Operations

-- =====================================================
-- Phase 1: Session Validation Foundation
-- =====================================================

-- 1.1 Core Session-Validation (using public schema due to permissions)
CREATE OR REPLACE FUNCTION public.validate_session_and_get_user(p_session_id TEXT)
RETURNS TABLE(user_id UUID, user_role TEXT, is_valid BOOLEAN)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
    -- Security: Null/Empty Check
    IF p_session_id IS NULL OR p_session_id = '' THEN
        RETURN QUERY SELECT NULL::UUID, NULL::TEXT, FALSE;
        RETURN;
    END IF;

    -- Use existing auth_sessions table
    RETURN QUERY
    SELECT
        s.user_id,
        s.user_role,
        TRUE as is_valid
    FROM auth_sessions s
    WHERE s.session_id = p_session_id
    AND s.expires_at > NOW()
    LIMIT 1;  -- Security: Only one Row

    -- If no valid session found
    IF NOT FOUND THEN
        RETURN QUERY SELECT NULL::UUID, NULL::TEXT, FALSE;
    END IF;
END;
$$;

-- Grant permissions for session validation
GRANT EXECUTE ON FUNCTION public.validate_session_and_get_user TO anon;
GRANT EXECUTE ON FUNCTION public.validate_session_and_get_user TO authenticated;

-- 1.2 API Schema Setup
CREATE SCHEMA IF NOT EXISTS api;
COMMENT ON SCHEMA api IS 'Session-based API functions for HttpOnly Cookie mode';
GRANT USAGE ON SCHEMA api TO anon, authenticated;

-- =====================================================
-- Phase 2: READ Operations (35 Functions)
-- =====================================================

-- 2.1 get_user_courses (replaces get_courses_by_creator)
CREATE OR REPLACE FUNCTION api.get_user_courses(p_session_id TEXT)
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

GRANT EXECUTE ON FUNCTION api.get_user_courses TO anon;

-- 2.2 get_user_learning_units (replaces get_learning_units_by_creator)
CREATE OR REPLACE FUNCTION api.get_user_learning_units(p_session_id TEXT)
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

GRANT EXECUTE ON FUNCTION api.get_user_learning_units TO anon;

-- 2.3 get_learning_unit (replaces get_learning_unit_by_id)
CREATE OR REPLACE FUNCTION api.get_learning_unit(p_session_id TEXT, p_unit_id UUID)
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

GRANT EXECUTE ON FUNCTION api.get_learning_unit TO anon;

-- =====================================================
-- Phase 3: WRITE Operations (21 Functions)
-- =====================================================

-- 3.1 create_learning_unit
CREATE OR REPLACE FUNCTION api.create_learning_unit(
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

GRANT EXECUTE ON FUNCTION api.create_learning_unit TO anon;

-- 3.2 create_course
CREATE OR REPLACE FUNCTION api.create_course(
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
    IF p_name IS NULL OR LENGTH(TRIM(p_name)) = 0 THEN
        RETURN QUERY SELECT
            NULL::UUID,
            NULL::TEXT,
            NULL::TIMESTAMPTZ,
            FALSE,
            'Kursname darf nicht leer sein'::TEXT;
        RETURN;
    END IF;

    -- Create record
    BEGIN
        INSERT INTO course (name, description, creator_id)
        VALUES (TRIM(p_name), NULLIF(TRIM(p_description), ''), v_user_id)
        RETURNING id INTO v_new_id;

        -- Success with data
        RETURN QUERY SELECT
            c.id,
            c.name,
            c.created_at,
            TRUE,
            NULL::TEXT
        FROM course c
        WHERE c.id = v_new_id;

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

GRANT EXECUTE ON FUNCTION api.create_course TO anon;

-- =====================================================
-- Phase 4: Additional critical READ Functions
-- =====================================================

-- 4.1 get_course_units (replaces get_assigned_units_for_course)
CREATE OR REPLACE FUNCTION api.get_course_units(p_session_id TEXT, p_course_id UUID)
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

GRANT EXECUTE ON FUNCTION api.get_course_units TO anon;

-- 4.2 get_unit_sections (replaces get_sections_for_unit)
CREATE OR REPLACE FUNCTION api.get_unit_sections(p_session_id TEXT, p_unit_id UUID)
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

GRANT EXECUTE ON FUNCTION api.get_unit_sections TO anon;

-- =====================================================
-- COMMENT: This is just the beginning of migration
-- =====================================================
-- This migration contains the critical foundation:
-- 1. Session Validation Function
-- 2. API Schema
-- 3. Top 5 READ Functions (courses, units, sections)
-- 4. Top 2 WRITE Functions (create unit, create course)
--
-- Remaining for next migration phase:
-- - 30 more READ Functions
-- - 19 more WRITE Functions
-- - 3 COMPLEX/RPC Functions
-- - Security Enhancements
--
-- Status: READY TO DEPLOY AND TEST FOUNDATION