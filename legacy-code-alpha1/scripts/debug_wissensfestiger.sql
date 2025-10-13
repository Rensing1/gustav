-- Debug-Skript für Wissensfestiger Problem
-- User: test1@test.de (de70c0c4-f095-47d6-a35a-dbec3f1f8cd4)
-- Kurs: Informatik

-- 1. Finde Kurs-ID für "Informatik"
SELECT id, title FROM courses WHERE title LIKE '%Informatik%';

-- 2. Zeige alle Mastery-Aufgaben im Kurs mit Prioritäten
WITH course_info AS (
    SELECT id FROM courses WHERE title LIKE '%Informatik%' LIMIT 1
),
student_info AS (
    SELECT 'de70c0c4-f095-47d6-a35a-dbec3f1f8cd4'::uuid as student_id
),
task_priorities AS (
    SELECT 
        amt.id as task_id,
        t.title,
        t.instruction,
        smp.next_due_date,
        smp.stability,
        smp.last_reviewed_at,
        CASE
            -- Never attempted: highest priority
            WHEN smp.id IS NULL THEN 1000
            -- Due for review (past next_due_date)
            WHEN smp.next_due_date IS NOT NULL AND smp.next_due_date <= CURRENT_DATE THEN 
                500 + (CURRENT_DATE - smp.next_due_date)
            -- Has attempts but not yet due
            WHEN smp.next_due_date IS NOT NULL AND smp.next_due_date > CURRENT_DATE THEN
                100 - (smp.next_due_date - CURRENT_DATE)
            -- Fallback for tasks with attempts but no review date
            ELSE 200
        END as priority_score,
        -- Zeige submission history
        (SELECT COUNT(*) FROM submission WHERE task_id = amt.id AND student_id = (SELECT student_id FROM student_info)) as total_submissions,
        (SELECT MAX(submitted_at) FROM submission WHERE task_id = amt.id AND student_id = (SELECT student_id FROM student_info)) as last_submission
    FROM all_mastery_tasks amt
    JOIN task_base t ON t.id = amt.id
    JOIN unit_section us ON us.id = amt.section_id
    JOIN learning_unit lu ON lu.id = us.unit_id
    JOIN course_learning_unit_assignment cua ON cua.unit_id = lu.id
    LEFT JOIN student_mastery_progress smp ON smp.task_id = amt.id AND smp.student_id = (SELECT student_id FROM student_info)
    WHERE cua.course_id = (SELECT id FROM course_info)
)
SELECT * FROM task_priorities ORDER BY priority_score DESC;

-- 3. Zeige ungelesenes Feedback
WITH course_info AS (
    SELECT id FROM courses WHERE title LIKE '%Informatik%' LIMIT 1
),
student_info AS (
    SELECT 'de70c0c4-f095-47d6-a35a-dbec3f1f8cd4'::uuid as student_id
)
SELECT 
    s.id as submission_id,
    s.task_id,
    t.title,
    t.instruction,
    s.submitted_at,
    s.feedback_viewed_at,
    s.ai_feedback IS NOT NULL as has_ai_feedback,
    s.teacher_override_feedback IS NOT NULL as has_teacher_feedback
FROM submission s
JOIN all_mastery_tasks amt ON amt.id = s.task_id
JOIN task_base t ON t.id = amt.id
JOIN unit_section us ON us.id = amt.section_id
JOIN learning_unit lu ON lu.id = us.unit_id
JOIN course_learning_unit_assignment cua ON cua.unit_id = lu.id
WHERE s.student_id = (SELECT student_id FROM student_info)
AND cua.course_id = (SELECT id FROM course_info)
AND s.feedback_viewed_at IS NULL
AND (s.ai_feedback IS NOT NULL OR s.teacher_override_feedback IS NOT NULL)
ORDER BY s.submitted_at DESC;

-- 4. Zeige die Aufgabe "Oder-Gatter" Details
SELECT 
    amt.id,
    t.title,
    t.instruction,
    smp.next_due_date,
    smp.stability,
    smp.last_reviewed_at
FROM all_mastery_tasks amt
JOIN task_base t ON t.id = amt.id
LEFT JOIN student_mastery_progress smp ON smp.task_id = amt.id AND smp.student_id = 'de70c0c4-f095-47d6-a35a-dbec3f1f8cd4'
WHERE t.instruction LIKE '%Oder-Gatter%';

-- 5. Zeige alle Submissions für Oder-Gatter Aufgabe
SELECT 
    s.id,
    s.submitted_at,
    s.feedback_viewed_at,
    s.is_correct,
    s.ai_feedback IS NOT NULL as has_feedback
FROM submission s
JOIN task_base t ON t.id = s.task_id
WHERE s.student_id = 'de70c0c4-f095-47d6-a35a-dbec3f1f8cd4'
AND t.instruction LIKE '%Oder-Gatter%'
ORDER BY s.submitted_at DESC;