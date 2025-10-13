-- Skript zum Erstellen von Testschülern für das Feedbackmodul
-- Dieses Skript muss mit Admin-Rechten ausgeführt werden

-- Trigger temporär deaktivieren
ALTER TABLE auth.users DISABLE TRIGGER on_auth_user_created;

-- Variablen für UUIDs
DO $$
DECLARE
    user1_id UUID := gen_random_uuid();
    user2_id UUID := gen_random_uuid();
BEGIN
    -- Testschüler 1: test1@test.de
    -- Prüfe ob User bereits existiert
    IF NOT EXISTS (SELECT 1 FROM auth.users WHERE email = 'test1@test.de') THEN
        INSERT INTO auth.users (
            id,
            email,
            encrypted_password,
            email_confirmed_at,
            created_at,
            updated_at,
            raw_app_meta_data,
            raw_user_meta_data
        ) VALUES (
            user1_id,
            'test1@test.de',
            crypt('123456', gen_salt('bf')),
            now(),
            now(),
            now(),
            '{"provider": "email", "providers": ["email"]}',
            '{}'
        );
        
        -- Profil für Testschüler 1
        INSERT INTO public.profiles (id, role, email, full_name)
        VALUES (user1_id, 'student', 'test1@test.de', 'Test Schüler 1');
        
        RAISE NOTICE 'Testschüler 1 (test1@test.de) wurde erfolgreich erstellt.';
    ELSE
        RAISE NOTICE 'Testschüler 1 (test1@test.de) existiert bereits.';
    END IF;

    -- Testschüler 2: test2@test.de
    -- Prüfe ob User bereits existiert
    IF NOT EXISTS (SELECT 1 FROM auth.users WHERE email = 'test2@test.de') THEN
        INSERT INTO auth.users (
            id,
            email,
            encrypted_password,
            email_confirmed_at,
            created_at,
            updated_at,
            raw_app_meta_data,
            raw_user_meta_data
        ) VALUES (
            user2_id,
            'test2@test.de',
            crypt('123456', gen_salt('bf')),
            now(),
            now(),
            now(),
            '{"provider": "email", "providers": ["email"]}',
            '{}'
        );
        
        -- Profil für Testschüler 2
        INSERT INTO public.profiles (id, role, email, full_name)
        VALUES (user2_id, 'student', 'test2@test.de', 'Test Schüler 2');
        
        RAISE NOTICE 'Testschüler 2 (test2@test.de) wurde erfolgreich erstellt.';
    ELSE
        RAISE NOTICE 'Testschüler 2 (test2@test.de) existiert bereits.';
    END IF;
END $$;

-- Trigger wieder aktivieren
ALTER TABLE auth.users ENABLE TRIGGER on_auth_user_created;

-- Ausgabe der erstellten Benutzer
SELECT 
    u.id,
    u.email,
    p.role,
    p.full_name,
    u.email_confirmed_at
FROM auth.users u
JOIN public.profiles p ON u.id = p.id
WHERE u.email IN ('test1@test.de', 'test2@test.de');