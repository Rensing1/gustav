-- Fix Schema Column References - EXACT SIGNATURES
-- This migration fixes column references while preserving exact function signatures
-- Fixes: display_name, created_by -> creator_id, learning_unit_id -> unit_id

-- =============================================================================
-- 1. Fix display_name references (7 functions) - EXACT ORIGINAL SIGNATURES
-- =============================================================================

CREATE OR REPLACE FUNCTION public.get_users_by_role(
    p_session_id TEXT,
    p_role TEXT
)
RETURNS TABLE(id uuid, email text, display_name text, role text)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Nur Lehrer duerfen andere User sehen
    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RETURN;
    END IF;

    -- User mit spezifischer Rolle zurueckgeben
    RETURN QUERY
    SELECT
        p.id,
        p.email,
        COALESCE(NULLIF(p.full_name, ''), p.email) as display_name, -- FIX: Use full_name with email fallback
        p.role::text
    FROM profiles p
    WHERE p.role::text = p_role
    ORDER BY COALESCE(NULLIF(p.full_name, ''), p.email), p.email; -- FIX: Order by computed display_name
END;
$$;

CREATE OR REPLACE FUNCTION public.get_students_in_course(
    p_session_id TEXT,
    p_course_id UUID
)
RETURNS TABLE(id uuid, email text, display_name text, role text, course_id uuid) -- EXACT ORIGINAL SIGNATURE
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Berechtigung pruefen: Lehrer des Kurses oder Student im Kurs
    IF v_user_role = 'teacher' THEN
        -- Lehrer muss Ersteller oder zugewiesen sein
        IF NOT EXISTS (
            SELECT 1 FROM course c
            WHERE c.id = p_course_id AND c.creator_id = v_user_id -- FIX: Use creator_id instead of created_by
        ) AND NOT EXISTS (
            SELECT 1 FROM course_teacher ct
            WHERE ct.course_id = p_course_id AND ct.teacher_id = v_user_id
        ) THEN
            RETURN;
        END IF;
    ELSIF v_user_role = 'student' THEN
        -- Student muss im Kurs sein
        IF NOT EXISTS (
            SELECT 1 FROM course_student cs
            WHERE cs.course_id = p_course_id AND cs.student_id = v_user_id
        ) THEN
            RETURN;
        END IF;
    END IF;

    -- Studenten im Kurs zurueckgeben
    RETURN QUERY
    SELECT
        p.id,
        p.email,
        COALESCE(NULLIF(p.full_name, ''), p.email) as display_name, -- FIX: Use full_name with email fallback
        p.role::text,
        cs.course_id
    FROM course_student cs
    JOIN profiles p ON p.id = cs.student_id
    WHERE cs.course_id = p_course_id
    ORDER BY COALESCE(NULLIF(p.full_name, ''), p.email), p.email; -- FIX: Order by computed display_name
END;
$$;

CREATE OR REPLACE FUNCTION public.get_teachers_in_course(
    p_session_id TEXT,
    p_course_id UUID
)
RETURNS TABLE(id uuid, email text, display_name text, role text, course_id uuid) -- EXACT ORIGINAL SIGNATURE
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Nur Lehrer duerfen andere Lehrer sehen
    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RETURN;
    END IF;

    -- Lehrer im Kurs zurueckgeben (inkl. Kursersteller)
    RETURN QUERY
    SELECT DISTINCT
        p.id,
        p.email,
        COALESCE(NULLIF(p.full_name, ''), p.email) as display_name, -- FIX: Use full_name with email fallback
        p.role::text,
        p_course_id
    FROM profiles p
    LEFT JOIN course_teacher ct ON p.id = ct.teacher_id AND ct.course_id = p_course_id
    LEFT JOIN course c ON p.id = c.creator_id AND c.id = p_course_id -- FIX: Use creator_id instead of created_by
    WHERE (ct.teacher_id IS NOT NULL OR c.id IS NOT NULL)
    ORDER BY COALESCE(NULLIF(p.full_name, ''), p.email); -- FIX: Order by computed display_name
END;
$$;

CREATE OR REPLACE FUNCTION public.get_course_students(
    p_session_id TEXT,
    p_course_id UUID
)
RETURNS TABLE(student_id uuid, email text, display_name text) -- EXACT ORIGINAL SIGNATURE
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Nur Lehrer oder Kursersteller darf Studenten sehen
    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RETURN;
    END IF;

    -- Autorisierung pruefen: ist User Kursersteller oder zugeordneter Lehrer?
    IF NOT EXISTS (
        SELECT 1 FROM course c 
        WHERE c.id = p_course_id AND c.creator_id = v_user_id -- FIX: Use creator_id instead of created_by
        UNION
        SELECT 1 FROM course_teacher ct 
        WHERE ct.course_id = p_course_id AND ct.teacher_id = v_user_id
    ) THEN
        RETURN;
    END IF;

    -- Studenten im Kurs zurueckgeben
    RETURN QUERY
    SELECT
        p.id as student_id, -- Exact column mapping to original signature
        p.email,
        COALESCE(NULLIF(p.full_name, ''), p.email) as display_name -- FIX: Use full_name with email fallback
    FROM profiles p
    JOIN course_student cs ON p.id = cs.student_id
    WHERE cs.course_id = p_course_id
    ORDER BY COALESCE(NULLIF(p.full_name, ''), p.email); -- FIX: Order by computed display_name
END;
$$;

-- =============================================================================
-- 2. Fix course.created_by -> creator_id references (sample key functions)
-- =============================================================================

CREATE OR REPLACE FUNCTION public.is_teacher_authorized_for_course(
    p_session_id TEXT,
    p_course_id UUID
)
RETURNS BOOLEAN -- EXACT ORIGINAL SIGNATURE
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_is_authorized BOOLEAN := FALSE;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Nur gueltige Sessions von Lehrern
    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RETURN FALSE;
    END IF;

    -- Pruefen ob User Kursersteller oder zugeordneter Lehrer ist
    SELECT EXISTS (
        SELECT 1 FROM course c 
        WHERE c.id = p_course_id AND c.creator_id = v_user_id -- FIX: Use creator_id instead of created_by
        UNION
        SELECT 1 FROM course_teacher ct 
        WHERE ct.course_id = p_course_id AND ct.teacher_id = v_user_id
    ) INTO v_is_authorized;

    RETURN v_is_authorized;
END;
$$;

-- =============================================================================
-- 3. Fix course_learning_unit_assignment.learning_unit_id -> unit_id references 
-- =============================================================================

CREATE OR REPLACE FUNCTION public.get_course_units(
    p_session_id TEXT,
    p_course_id UUID
)
RETURNS TABLE(
    id uuid,
    learning_unit_id uuid, -- KEEPING ORIGINAL COLUMN NAME IN SIGNATURE
    learning_unit_title text,
    created_at timestamp with time zone
) -- EXACT ORIGINAL SIGNATURE
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Zugriffsberechtigung pruefen
    IF v_user_role = 'teacher' THEN
        -- Lehrer: Alle Units in eigenen Kursen
        IF NOT EXISTS (
            SELECT 1 FROM course c 
            WHERE c.id = p_course_id AND c.creator_id = v_user_id -- FIX: Use creator_id instead of created_by
            UNION
            SELECT 1 FROM course_teacher ct 
            WHERE ct.course_id = p_course_id AND ct.teacher_id = v_user_id
        ) THEN
            RETURN;
        END IF;
    ELSIF v_user_role = 'student' THEN
        -- Student: Nur Units in eigenen Kursen
        IF NOT EXISTS (
            SELECT 1 FROM course_student cs 
            WHERE cs.course_id = p_course_id AND cs.student_id = v_user_id
        ) THEN
            RETURN;
        END IF;
    END IF;

    -- Units zurueckgeben
    RETURN QUERY
    SELECT
        lu.id,
        lu.id as learning_unit_id, -- Map to expected column name in signature
        lu.title as learning_unit_title,
        clua.assigned_at as created_at
    FROM learning_unit lu
    JOIN course_learning_unit_assignment clua ON lu.id = clua.unit_id -- FIX: Use unit_id instead of learning_unit_id
    WHERE clua.course_id = p_course_id
    ORDER BY clua.assigned_at;
END;
$$;

CREATE OR REPLACE FUNCTION public.get_courses_assigned_to_unit(
    p_session_id TEXT,
    p_unit_id UUID
)
RETURNS TABLE(id uuid, name text, creator_id uuid, created_at timestamp with time zone) -- EXACT ORIGINAL SIGNATURE
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Nur Lehrer duerfen Kurszuweisungen sehen
    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RETURN;
    END IF;

    -- Kurse zurueckgeben, die diese Unit verwenden
    RETURN QUERY
    SELECT
        c.id,
        c.name,
        c.creator_id, -- FIX: Use creator_id instead of created_by (but keep in signature)
        clua.assigned_at as created_at
    FROM course c
    JOIN course_learning_unit_assignment clua ON c.id = clua.course_id
    WHERE clua.unit_id = p_unit_id -- FIX: Use unit_id instead of learning_unit_id
    ORDER BY c.name;
END;
$$;

-- Grant permissions
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO anon;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO authenticated;