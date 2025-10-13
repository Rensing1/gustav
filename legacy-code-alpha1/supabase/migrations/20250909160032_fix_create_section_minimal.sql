-- Fix create_section to use correct column names: unit_id instead of learning_unit_id

-- Drop existing function with all possible parameter combinations
DROP FUNCTION IF EXISTS public.create_section(TEXT, UUID, TEXT);
DROP FUNCTION IF EXISTS public.create_section(TEXT, UUID, TEXT, TEXT);
DROP FUNCTION IF EXISTS public.create_section(TEXT, UUID, TEXT, TEXT, JSONB);

-- Create corrected function
CREATE OR REPLACE FUNCTION public.create_section(
    p_session_id TEXT,
    p_unit_id UUID,
    p_title TEXT,
    p_description TEXT DEFAULT NULL,  -- Keep for compatibility but ignore since column doesn't exist
    p_materials JSONB DEFAULT NULL
)
RETURNS UUID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_section_id UUID;
    v_order_in_unit INT;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can create sections';
    END IF;

    -- Check if teacher owns the learning unit
    IF NOT EXISTS (
        SELECT 1 FROM learning_unit 
        WHERE id = p_unit_id AND creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Get next order position
    SELECT COALESCE(MAX(order_in_unit), 0) + 1
    INTO v_order_in_unit
    FROM unit_section
    WHERE unit_id = p_unit_id;  -- Fixed: using unit_id

    -- Create section (without description since column doesn't exist)
    INSERT INTO unit_section (
        unit_id,  -- Fixed: using unit_id
        title,
        materials,
        order_in_unit
    )
    VALUES (
        p_unit_id,
        p_title,
        p_materials,
        v_order_in_unit
    )
    RETURNING id INTO v_section_id;

    RETURN v_section_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.create_section TO anon;