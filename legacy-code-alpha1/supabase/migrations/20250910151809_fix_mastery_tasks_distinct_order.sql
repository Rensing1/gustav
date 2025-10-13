-- Fix SELECT DISTINCT with ORDER BY issue in get_mastery_tasks_for_course

CREATE OR REPLACE FUNCTION public.get_mastery_tasks_for_course(
    p_session_id text, 
    p_course_id uuid
)
RETURNS TABLE(
    task_id uuid,
    task_title text,
    task_type text,
    unit_id uuid,
    unit_title text,
    section_id uuid,
    section_title text,
    review_after timestamp with time zone,
    proficiency_score numeric
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = 'public'
AS $function$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid THEN
        RAISE EXCEPTION 'Invalid session';
    END IF;
    
    -- Check if user is enrolled in course or is the teacher
    IF v_user_role = 'student' THEN
        IF NOT EXISTS (
            SELECT 1 FROM course_student 
            WHERE course_id = p_course_id AND student_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Student not enrolled in course';
        END IF;
    ELSIF v_user_role = 'teacher' THEN
        IF NOT EXISTS (
            SELECT 1 FROM course 
            WHERE id = p_course_id AND creator_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Teacher does not own this course';
        END IF;
    END IF;
    
    -- Get all mastery tasks for the course
    -- Removed DISTINCT and added columns needed for ORDER BY
    RETURN QUERY
    SELECT 
        tb.id as task_id,
        tb.instruction as task_title,
        tb.task_type,
        lu.id as unit_id,
        lu.title as unit_title,
        us.id as section_id,
        us.title as section_title,
        -- Convert next_due_date to timestamp for review_after
        CASE 
            WHEN smp.next_due_date IS NOT NULL THEN 
                smp.next_due_date::timestamp AT TIME ZONE 'UTC'
            ELSE 
                NULL::timestamp with time zone
        END as review_after,
        smp.difficulty::NUMERIC as proficiency_score
    FROM task_base tb
    JOIN unit_section us ON us.id = tb.section_id
    JOIN learning_unit lu ON lu.id = us.unit_id
    JOIN course_learning_unit_assignment cla ON cla.unit_id = lu.id
    LEFT JOIN student_mastery_progress smp ON 
        smp.student_id = v_user_id AND
        smp.task_id = tb.id  
    WHERE cla.course_id = p_course_id 
        AND tb.task_type = 'mastery_task'
    ORDER BY lu.title, us.order_in_unit, tb.order_in_section;
END;
$function$;