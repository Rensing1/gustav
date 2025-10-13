-- Fix PostgreSQL Functions Schema Mismatch
-- PostgreSQL Functions an reales Datenschema anpassen
-- Datum: 2025-01-09

-- =====================================================
-- Problem: Schema-Mismatch zwischen Functions und Real Schema
-- =====================================================
-- 1. unit_assignment -> course_learning_unit_assignment 
-- 2. section -> unit_section
-- 3. lu.description -> entfernen (Spalte existiert nicht)

-- =====================================================
-- Step 1: DROP existing functions (to allow return type changes)
-- =====================================================

DROP FUNCTION IF EXISTS public.get_learning_unit(TEXT, UUID);
DROP FUNCTION IF EXISTS public.get_user_learning_units(TEXT);
DROP FUNCTION IF EXISTS public.get_course_units(TEXT, UUID);
DROP FUNCTION IF EXISTS public.get_unit_sections(TEXT, UUID);

-- =====================================================
-- Fix 1: get_learning_unit() - description entfernen
-- =====================================================

CREATE OR REPLACE FUNCTION public.get_learning_unit(p_session_id TEXT, p_unit_id UUID)
RETURNS TABLE(
    id UUID,
    title TEXT,
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

    -- Load Learning Unit with authorization (OHNE description)
    RETURN QUERY
    SELECT
        lu.id,
        lu.title,
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
            FROM course_learning_unit_assignment clua
            INNER JOIN course_student cs ON cs.course_id = clua.course_id
            WHERE clua.unit_id = lu.id
            AND cs.student_id = v_user_id
        )
    );
END;
$$;

-- =====================================================
-- Fix 2: get_user_learning_units() - description entfernen
-- =====================================================

CREATE OR REPLACE FUNCTION public.get_user_learning_units(p_session_id TEXT)
RETURNS TABLE(
    id UUID,
    title TEXT,
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

    -- Only Teacher can see own Learning Units (OHNE description)
    IF v_user_role = 'teacher' THEN
        RETURN QUERY
        SELECT
            lu.id,
            lu.title,
            lu.creator_id,
            lu.created_at,
            COUNT(DISTINCT clua.course_id)::INT as assignment_count
        FROM learning_unit lu
        LEFT JOIN course_learning_unit_assignment clua ON clua.unit_id = lu.id
        WHERE lu.creator_id = v_user_id
        GROUP BY lu.id, lu.title, lu.creator_id, lu.created_at
        ORDER BY lu.created_at DESC;
    END IF;
    -- Students don't see Learning Units in management view
END;
$$;

-- =====================================================
-- Fix 3: get_course_units() - unit_assignment -> course_learning_unit_assignment
-- =====================================================

CREATE OR REPLACE FUNCTION public.get_course_units(p_session_id TEXT, p_course_id UUID)
RETURNS TABLE(
    id UUID,
    learning_unit_id UUID,
    learning_unit_title TEXT,
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

    -- Check access authorization and load units (mit course_learning_unit_assignment)
    RETURN QUERY
    SELECT
        clua.unit_id as id,
        clua.unit_id as learning_unit_id,
        lu.title as learning_unit_title,
        clua.assigned_at as created_at
    FROM course_learning_unit_assignment clua
    INNER JOIN learning_unit lu ON lu.id = clua.unit_id
    INNER JOIN course c ON c.id = clua.course_id
    WHERE clua.course_id = p_course_id
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
    ORDER BY clua.assigned_at ASC;
END;
$$;

-- =====================================================
-- Fix 4: get_unit_sections() - section -> unit_section
-- =====================================================

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

    -- Check access authorization and load sections (mit unit_section, OHNE content/section_type)
    RETURN QUERY
    SELECT
        us.id,
        us.title,
        NULL::TEXT as content,      -- Spalte existiert nicht in unit_section
        'section'::TEXT as section_type,  -- Default value
        us.order_in_unit as "position",
        us.created_at
    FROM unit_section us
    INNER JOIN learning_unit lu ON lu.id = us.unit_id
    WHERE us.unit_id = p_unit_id
    AND (
        lu.creator_id = v_user_id  -- Unit Owner
        OR v_user_role = 'admin'   -- Admin
        OR EXISTS (                -- Student with access through Course Assignment
            SELECT 1 
            FROM course_learning_unit_assignment clua
            INNER JOIN course_student cs ON cs.course_id = clua.course_id
            WHERE clua.unit_id = p_unit_id
            AND cs.student_id = v_user_id
        )
    )
    ORDER BY us.order_in_unit ASC, us.created_at ASC;
END;
$$;

-- =====================================================
-- Status: Schema-Mismatch behoben
-- =====================================================
-- Alle PostgreSQL Functions nutzen jetzt das reale Datenschema:
-- 1. course_learning_unit_assignment statt unit_assignment
-- 2. unit_section statt section  
-- 3. Entfernte nicht-existierende Spalten (description, content, section_type)
-- 4. Angepasste Return-Strukturen f�r Python Wrapper Kompatibilit�t