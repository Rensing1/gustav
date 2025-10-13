-- Erstelle Tabelle für erlaubte E-Mail-Domains
CREATE TABLE IF NOT EXISTS allowed_email_domains (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    domain TEXT NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Füge @gymalf.de als erlaubte Domain hinzu
INSERT INTO allowed_email_domains (domain) VALUES ('@gymalf.de');

-- Erstelle Index für schnelle Domain-Lookups
CREATE INDEX idx_allowed_email_domains_domain ON allowed_email_domains(domain);

-- RLS für allowed_email_domains
ALTER TABLE allowed_email_domains ENABLE ROW LEVEL SECURITY;

-- Nur Service Role kann Domains verwalten, aber alle authentifizierten User können sie lesen
CREATE POLICY "Authenticated users can view active allowed domains" ON allowed_email_domains
    FOR SELECT
    TO authenticated
    USING (is_active = true);

-- Aktualisiere die handle_new_user Funktion mit Domain-Validierung
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
DECLARE
    email_domain TEXT;
    is_domain_allowed BOOLEAN;
BEGIN
    -- Extrahiere die Domain aus der E-Mail-Adresse
    email_domain := LOWER(SUBSTRING(NEW.email FROM '@[^@]+$'));
    
    -- Prüfe, ob die Domain erlaubt ist
    SELECT EXISTS(
        SELECT 1 FROM allowed_email_domains 
        WHERE LOWER(domain) = email_domain 
        AND is_active = true
    ) INTO is_domain_allowed;
    
    -- Wenn die Domain nicht erlaubt ist, werfe einen Fehler
    IF NOT is_domain_allowed THEN
        RAISE EXCEPTION 'Registrierung nur mit schulischen E-Mail-Adressen (@gymalf.de) möglich.';
    END IF;
    
    -- Erstelle das Profil mit Standard-Rolle 'student'
    INSERT INTO public.profiles (id, role, username)
    VALUES (NEW.id, 'student', NEW.email);
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;