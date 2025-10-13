-- Add @test.de to the list of allowed email domains for testing purposes
INSERT INTO public.allowed_email_domains (domain, is_active)
VALUES ('@test.de', true)
ON CONFLICT (domain) DO NOTHING;
