-- Hilfsskript zur Verwaltung der erlaubten E-Mail-Domains

-- Alle erlaubten Domains anzeigen
SELECT domain, is_active, created_at 
FROM allowed_email_domains 
ORDER BY domain;

-- Neue Domain hinzufügen (Beispiel)
-- INSERT INTO allowed_email_domains (domain) VALUES ('@lehrer.gymalf.de');

-- Domain deaktivieren (soft delete)
-- UPDATE allowed_email_domains SET is_active = false WHERE domain = '@example.de';

-- Domain wieder aktivieren
-- UPDATE allowed_email_domains SET is_active = true WHERE domain = '@example.de';

-- Prüfen, ob eine bestimmte E-Mail erlaubt ist
-- SELECT EXISTS(
--     SELECT 1 FROM allowed_email_domains 
--     WHERE LOWER('@student@gymalf.de') LIKE '%' || LOWER(domain) 
--     AND is_active = true
-- );