-- Fix RPC functions to use new task separation views instead of old task.is_mastery column

-- Fix get_mastery_summary function
CREATE OR REPLACE FUNCTION public.get_mastery_summary(p_student_id uuid, p_course_id uuid)
 RETURNS TABLE(total integer, mastered integer, learning integer, not_started integer, due_today integer, avg_stability double precision)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(t.*)::INTEGER as total,
        COUNT(CASE WHEN smp.stability > 21 THEN 1 END)::INTEGER as mastered,
        COUNT(CASE WHEN smp.stability BETWEEN 0.1 AND 21 THEN 1 END)::INTEGER as learning,
        COUNT(CASE WHEN smp.stability IS NULL OR smp.stability = 0 THEN 1 END)::INTEGER as not_started,
        COUNT(CASE WHEN smp.next_due_date <= CURRENT_DATE THEN 1 END)::INTEGER as due_today,
        AVG(CASE WHEN smp.stability > 0 THEN smp.stability END)::FLOAT as avg_stability
    FROM all_mastery_tasks t
    JOIN unit_section us ON t.section_id = us.id
    JOIN learning_unit lu ON us.unit_id = lu.id
    JOIN course_learning_unit_assignment clua ON lu.id = clua.unit_id
    LEFT JOIN student_mastery_progress smp
        ON t.id = smp.task_id AND smp.student_id = p_student_id
    WHERE clua.course_id = p_course_id;
END;
$function$;

-- Fix get_due_tomorrow_count function
CREATE OR REPLACE FUNCTION public.get_due_tomorrow_count(p_student_id uuid, p_course_id uuid)
 RETURNS integer
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
    tomorrow_date DATE := CURRENT_DATE + INTERVAL '1 day';
    due_count INTEGER;
BEGIN
    SELECT COUNT(*)::INTEGER
    INTO due_count
    FROM all_mastery_tasks t
    JOIN unit_section us ON t.section_id = us.id
    JOIN learning_unit lu ON us.unit_id = lu.id
    JOIN course_learning_unit_assignment clua ON lu.id = clua.unit_id
    JOIN student_mastery_progress smp
        ON t.id = smp.task_id AND smp.student_id = p_student_id
    WHERE clua.course_id = p_course_id
        AND smp.next_due_date = tomorrow_date;
        
    RETURN COALESCE(due_count, 0);
END;
$function$;

-- Comment: These functions were using the old task table with is_mastery column
-- After Phase 4 cleanup, they need to use the all_mastery_tasks view instead