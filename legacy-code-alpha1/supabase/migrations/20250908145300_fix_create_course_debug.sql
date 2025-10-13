-- Fix create_course function with better error handling

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
    v_course_record RECORD;
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
        INSERT INTO course (name, creator_id)
        VALUES (TRIM(p_name), v_user_id)
        RETURNING course.id, course.name, course.created_at INTO v_course_record;

        -- Success with data
        RETURN QUERY SELECT
            v_course_record.id,
            v_course_record.name,
            v_course_record.created_at,
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
        WHEN foreign_key_violation THEN
            RETURN QUERY SELECT
                NULL::UUID,
                NULL::TEXT,
                NULL::TIMESTAMPTZ,
                FALSE,
                ('Foreign Key Fehler - User ID: ' || v_user_id::TEXT)::TEXT;
        WHEN OTHERS THEN
            RETURN QUERY SELECT
                NULL::UUID,
                NULL::TEXT,
                NULL::TIMESTAMPTZ,
                FALSE,
                ('SQL Error: ' || SQLSTATE || ' - ' || SQLERRM)::TEXT;
    END;
END;
$$;

GRANT EXECUTE ON FUNCTION api.create_course TO anon;