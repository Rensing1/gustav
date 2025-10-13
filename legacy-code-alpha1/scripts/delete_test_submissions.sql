-- SQL-Skript zum Löschen aller Submissions von test1@test.de
-- Usage: psql "postgresql://postgres:postgres@127.0.0.1:54322/postgres" -f delete_test_submissions.sql

-- Anzeige der zu löschenden Submissions vor dem Löschen
SELECT 
    'Submissions vor dem Löschen:' as info,
    COUNT(*) as anzahl_submissions
FROM submission s 
JOIN auth.users u ON s.student_id = u.id 
WHERE u.email = 'test1@test.de';

-- Anzeige der Details der zu löschenden Submissions
SELECT 
    s.id,
    s.task_id,
    s.submitted_at,
    u.email
FROM submission s 
JOIN auth.users u ON s.student_id = u.id 
WHERE u.email = 'test1@test.de'
ORDER BY s.submitted_at DESC;

-- Löschen aller Submissions für test1@test.de
DELETE FROM submission 
WHERE student_id = (
    SELECT id FROM auth.users WHERE email = 'test1@test.de'
);

-- Verifikation: Prüfung ob alle Submissions gelöscht wurden
SELECT 
    'Submissions nach dem Löschen:' as info,
    COUNT(*) as anzahl_submissions
FROM submission s 
JOIN auth.users u ON s.student_id = u.id 
WHERE u.email = 'test1@test.de';