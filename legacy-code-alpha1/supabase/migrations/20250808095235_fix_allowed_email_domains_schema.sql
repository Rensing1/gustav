-- Fix: Ensure handle_new_user trigger finds allowed_email_domains table in public schema
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
DECLARE
    email_domain TEXT;
    is_domain_allowed BOOLEAN;
BEGIN
    -- Extract domain from email address
    email_domain := LOWER(SUBSTRING(NEW.email FROM '@[^@]+$'));
    
    -- Check if domain is allowed (with explicit public schema)
    SELECT EXISTS(
        SELECT 1 FROM public.allowed_email_domains 
        WHERE LOWER(domain) = email_domain 
        AND is_active = true
    ) INTO is_domain_allowed;
    
    -- If domain is not allowed, raise exception
    IF NOT is_domain_allowed THEN
        RAISE EXCEPTION 'Registration only allowed with school email addresses (@gymalf.de).';
    END IF;
    
    -- Create profile with default role 'student'
    INSERT INTO public.profiles (id, role, username)
    VALUES (NEW.id, 'student', NEW.email);
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;