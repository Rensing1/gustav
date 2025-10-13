-- Fix create_course function using explicit variables (Option 1)
-- This fixes the column ambiguity issue identified in Phase 2
-- Solution: Use result_* variables to avoid namespace collision with RETURNS TABLE

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

GRANT EXECUTE ON FUNCTION api.create_course TO anon;