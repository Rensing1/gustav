-- GUSTAV: Analyse der Schüler-Kurs-Zuordnungen
-- Erstellt: 2025-09-03
-- Zweck: Identifizierung von Schülern ohne Kurszuordnung und Mehrfachzuordnungen

-- =============================================================================
-- 1. SCHÜLER OHNE KURSZUORDNUNG
-- =============================================================================
-- Alle Schüler, die keinem Kurs zugeordnet sind
SELECT 
    p.id,
    p.email,
    p.full_name,
    p.created_at
FROM profiles p
WHERE p.role = 'student'
AND p.id NOT IN (
    SELECT DISTINCT student_id 
    FROM course_student
    WHERE student_id IS NOT NULL
);

-- =============================================================================
-- 2. SCHÜLER MIT MEHREREN KURSZUORDNUNGEN
-- =============================================================================
-- Schüler, die mehreren Kursen zugeordnet sind (mit Anzahl)
SELECT 
    p.id,
    p.email,
    p.full_name,
    COUNT(cs.course_id) as anzahl_kurse,
    STRING_AGG(c.name, ', ' ORDER BY c.name) as kurse
FROM profiles p
JOIN course_student cs ON p.id = cs.student_id
JOIN course c ON cs.course_id = c.id
WHERE p.role = 'student'
GROUP BY p.id, p.email, p.full_name
HAVING COUNT(cs.course_id) > 1
ORDER BY anzahl_kurse DESC, p.full_name;

-- =============================================================================
-- 3. VOLLSTÄNDIGE ÜBERSICHT ALLER SCHÜLER-KURS-ZUORDNUNGEN
-- =============================================================================
-- Vollständige Übersicht der Schüler-Kurs-Zuordnungen (sortiert nach Kurs)
SELECT 
    p.id as student_id,
    p.email,
    p.full_name,
    CASE 
        WHEN cs.course_id IS NULL THEN 'Kein Kurs zugeordnet'
        ELSE c.name
    END as kurs_name,
    cs.enrolled_at,
    COUNT(cs.course_id) OVER (PARTITION BY p.id) as anzahl_kurse_gesamt
FROM profiles p
LEFT JOIN course_student cs ON p.id = cs.student_id
LEFT JOIN course c ON cs.course_id = c.id
WHERE p.role = 'student'
ORDER BY kurs_name, p.full_name;

-- =============================================================================
-- USAGE NOTES
-- =============================================================================
-- Diese Abfragen können einzeln oder gemeinsam ausgeführt werden:
-- 
-- psql "postgresql://postgres:postgres@127.0.0.1:54322/postgres" -f analyze_student_course_assignments.sql
--
-- Oder für lokale Supabase-Instanz:
-- supabase db reset && psql $(supabase status | grep "DB URL" | awk '{print $3}') -f analyze_student_course_assignments.sql