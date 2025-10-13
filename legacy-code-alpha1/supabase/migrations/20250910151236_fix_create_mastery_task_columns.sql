-- Fix create_mastery_task function to match actual mastery_tasks table schema

CREATE OR REPLACE FUNCTION public.create_mastery_task(
    p_session_id text, 
    p_section_id uuid, 
    p_instruction text, 
    p_task_type text, 
    p_order_in_section integer DEFAULT 1, 
    p_difficulty_level integer DEFAULT 1, 
    p_assessment_criteria jsonb DEFAULT NULL::jsonb
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = 'public'
AS $function$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_task_id UUID;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can create tasks';
    END IF;

    -- Check if teacher has access to the section
    IF NOT EXISTS (
        SELECT 1 
        FROM unit_section s
        JOIN learning_unit lu ON lu.id = s.unit_id
        WHERE s.id = p_section_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Begin transaction
    BEGIN
        -- Step 1: Insert into task_base with instruction
        INSERT INTO task_base (section_id, instruction, task_type, order_in_section, assessment_criteria)
        VALUES (p_section_id, p_instruction, p_task_type, p_order_in_section, p_assessment_criteria)
        RETURNING id INTO v_task_id;

        -- Step 2: Insert into mastery_tasks with correct columns
        INSERT INTO mastery_tasks (task_id, difficulty_level, spaced_repetition_interval)
        VALUES (v_task_id, p_difficulty_level, 1);  -- Default interval of 1 day

        RETURN v_task_id;
    EXCEPTION
        WHEN OTHERS THEN
            -- Rollback will happen automatically
            RAISE;
    END;
END;
$function$;

-- Fix get_mastery_tasks_for_course function to properly calculate review_after
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
    
    -- Get all mastery tasks for the course with proper joins
    RETURN QUERY
    SELECT DISTINCT
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