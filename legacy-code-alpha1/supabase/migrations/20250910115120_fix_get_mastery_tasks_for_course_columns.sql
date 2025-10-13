-- Fix get_mastery_tasks_for_course to include all required fields
-- Add difficulty_level and solution_hints (instead of concept_explanation)

-- Drop existing function first because we're changing the return type
DROP FUNCTION IF EXISTS public.get_mastery_tasks_for_course(text, uuid);

CREATE OR REPLACE FUNCTION public.get_mastery_tasks_for_course(p_session_id text, p_course_id uuid)
RETURNS TABLE(
    task_id uuid, 
    title text, 
    instruction text, 
    section_title text, 
    unit_title text, 
    spaced_repetition_interval integer,
    difficulty_level integer,
    solution_hints text
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
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

    -- Check if user can access this course
    IF v_user_role = 'teacher' THEN
        -- Teachers can only view mastery tasks for courses they teach or own
        IF NOT EXISTS (
            SELECT 1 FROM course c
            WHERE c.id = p_course_id 
            AND (c.creator_id = v_user_id OR EXISTS (
                SELECT 1 FROM course_teacher ct 
                WHERE ct.course_id = c.id AND ct.teacher_id = v_user_id
            ))
        ) THEN
            RAISE EXCEPTION 'Unauthorized: Only teachers can view mastery tasks for course';
        END IF;
    ELSE
        -- Students can only view mastery tasks for courses they're enrolled in
        IF NOT EXISTS (
            SELECT 1 FROM course_student cs 
            WHERE cs.course_id = p_course_id AND cs.student_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Unauthorized: Student not enrolled in this course';
        END IF;
    END IF;

    RETURN QUERY
    SELECT 
        tb.id as task_id,
        tb.title,
        tb.instruction,
        us.title as section_title,
        lu.title as unit_title,
        mt.spaced_repetition_interval,
        mt.difficulty_level,
        tb.solution_hints  -- Changed from concept_explanation
    FROM task_base tb
    JOIN mastery_tasks mt ON mt.task_id = tb.id
    JOIN unit_section us ON us.id = tb.section_id
    JOIN learning_unit lu ON lu.id = us.unit_id
    JOIN course_learning_unit_assignment cua ON cua.unit_id = lu.id
    WHERE cua.course_id = p_course_id
    ORDER BY us.order_in_unit, tb.title;
END;
$function$;

-- Ensure permissions remain
GRANT EXECUTE ON FUNCTION public.get_mastery_tasks_for_course TO anon;

-- Update comment
COMMENT ON FUNCTION public.get_mastery_tasks_for_course IS 'Get all mastery tasks for a course with task details including difficulty level and solution hints';

-- Since concept_explanation is always NULL and not used, we could drop it
-- But let's be careful and only do this if you explicitly confirm
-- ALTER TABLE mastery_tasks DROP COLUMN concept_explanation;