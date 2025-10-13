-- Fix all references from p.display_name to p.full_name using dynamic SQL
-- This preserves the exact function signatures

DO $$
DECLARE
    func_name text;
    func_def text;
BEGIN
    -- Get list of functions that need fixing
    FOR func_name IN 
        SELECT proname::text 
        FROM pg_proc 
        WHERE prosrc LIKE '%display_name%' 
        AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
    LOOP
        -- Get function definition and replace display_name with full_name
        SELECT pg_get_functiondef(oid) INTO func_def
        FROM pg_proc
        WHERE proname = func_name
        AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
        LIMIT 1;
        
        -- Replace p.display_name with p.full_name
        func_def := REPLACE(func_def, 'p.display_name', 'p.full_name');
        
        -- Also handle cases where it might be referenced differently
        func_def := REPLACE(func_def, 'profiles.display_name', 'profiles.full_name');
        
        -- Execute the updated function definition
        EXECUTE func_def;
        
        RAISE NOTICE 'Updated function: %', func_name;
    END LOOP;
END $$;