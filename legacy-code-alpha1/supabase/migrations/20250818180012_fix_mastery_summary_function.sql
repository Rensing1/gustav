-- Migration: Fix mastery summary function to use correct table relationships
-- Description: Updates the get_mastery_summary function to join through unit_section and learning_unit

-- Drop existing functions
DROP FUNCTION IF EXISTS get_mastery_summary(UUID, UUID);
DROP FUNCTION IF EXISTS get_due_tomorrow_count(UUID, UUID);

-- Recreate function with correct joins
CREATE OR REPLACE FUNCTION get_mastery_summary(
    p_student_id UUID,
    p_course_id UUID
)
RETURNS TABLE (
    total INTEGER,
    mastered INTEGER,
    learning INTEGER,
    not_started INTEGER,
    due_today INTEGER,
    avg_stability FLOAT
) 
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(t.*)::INTEGER as total,
        COUNT(CASE WHEN smp.stability > 21 THEN 1 END)::INTEGER as mastered,
        COUNT(CASE WHEN smp.stability BETWEEN 0.1 AND 21 THEN 1 END)::INTEGER as learning,
        COUNT(CASE WHEN smp.stability IS NULL OR smp.stability = 0 THEN 1 END)::INTEGER as not_started,
        COUNT(CASE WHEN smp.next_due_date <= CURRENT_DATE THEN 1 END)::INTEGER as due_today,
        AVG(CASE WHEN smp.stability > 0 THEN smp.stability END)::FLOAT as avg_stability
    FROM task t
    JOIN unit_section us ON t.section_id = us.id
    JOIN learning_unit lu ON us.unit_id = lu.id
    LEFT JOIN student_mastery_progress smp 
        ON t.id = smp.task_id AND smp.student_id = p_student_id
    WHERE lu.course_id = p_course_id 
        AND t.is_mastery = true;
END;
$$;

-- Recreate function for tomorrow's due tasks
CREATE OR REPLACE FUNCTION get_due_tomorrow_count(
    p_student_id UUID,
    p_course_id UUID
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    tomorrow_date DATE := CURRENT_DATE + INTERVAL '1 day';
    due_count INTEGER;
BEGIN
    SELECT COUNT(*)::INTEGER
    INTO due_count
    FROM task t
    JOIN unit_section us ON t.section_id = us.id
    JOIN learning_unit lu ON us.unit_id = lu.id
    JOIN student_mastery_progress smp 
        ON t.id = smp.task_id AND smp.student_id = p_student_id
    WHERE lu.course_id = p_course_id 
        AND t.is_mastery = true
        AND smp.next_due_date = tomorrow_date;
    
    RETURN COALESCE(due_count, 0);
END;
$$;

-- Grant execute permissions to authenticated users
GRANT EXECUTE ON FUNCTION get_mastery_summary TO authenticated;
GRANT EXECUTE ON FUNCTION get_due_tomorrow_count TO authenticated;

-- Add comments for documentation
COMMENT ON FUNCTION get_mastery_summary IS 'Returns aggregated mastery statistics for a student in a specific course - fixed version with proper joins';
COMMENT ON FUNCTION get_due_tomorrow_count IS 'Returns count of mastery tasks due tomorrow for a student in a specific course - fixed version with proper joins';