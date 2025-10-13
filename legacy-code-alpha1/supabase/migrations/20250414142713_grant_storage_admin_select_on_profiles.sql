-- Grant SELECT permission on the profiles table to the internal storage admin role
-- This allows the storage RLS policy check (WITH CHECK clause) to read the user's role.

-- Grant usage on the schema (might already exist, but safe to include)
GRANT USAGE ON SCHEMA public TO supabase_storage_admin;

-- Grant select specifically on the profiles table
GRANT SELECT ON public.profiles TO supabase_storage_admin;

-- Grant usage on the ENUM type (might already exist)
GRANT USAGE ON TYPE public.user_role TO supabase_storage_admin;

-- WICHTIG: Wir müssen RLS für diesen internen Nutzer NICHT umgehen.
-- Die RLS-Policy auf storage.objects wird im Kontext des anfragenden Users (auth.uid())
-- ausgewertet. Der storage_admin braucht nur die grundsätzliche Leseberechtigung,
-- um die Subquery `(SELECT role FROM public.profiles WHERE id = auth.uid())` ausführen zu können.