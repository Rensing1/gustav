-- Fix create_learning_unit function - remove non-existent description column
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

    -- Create record (without description column)
    BEGIN
        INSERT INTO learning_unit (title, creator_id)
        VALUES (TRIM(p_title), v_user_id)
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
                'Fehler beim Erstellen der Lerneinheit: ' || SQLERRM;
    END;
END;
$$;

GRANT EXECUTE ON FUNCTION public.create_learning_unit TO anon;