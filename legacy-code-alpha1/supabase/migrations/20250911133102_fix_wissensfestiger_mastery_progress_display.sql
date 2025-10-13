-- Fix Wissensfestiger issues:
-- 1. Include mastery_progress data in task responses to show correct status
-- 2. Fix task repetition by properly clearing session state

-- Drop and recreate the function to include mastery progress data
DROP FUNCTION IF EXISTS public.get_next_mastery_task_or_unviewed_feedback(TEXT, UUID, UUID);

CREATE OR REPLACE FUNCTION public.get_next_mastery_task_or_unviewed_feedback(
    p_session_id TEXT,
    p_student_id UUID,
    p_course_id UUID
)
RETURNS JSON
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_submission_id UUID;
    v_task_id UUID;
    v_result JSON;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RAISE EXCEPTION 'Invalid session';
    END IF;

    -- Verify that the user is a student and matches the requested student_id
    IF v_user_role != 'student' OR v_user_id != p_student_id THEN
        RAISE EXCEPTION 'Unauthorized: Must be the student';
    END IF;

    -- Verify student is enrolled in the course
    IF NOT EXISTS (
        SELECT 1 FROM course_student 
        WHERE student_id = v_user_id 
        AND course_id = p_course_id
    ) THEN
        RAISE EXCEPTION 'Student not enrolled in course';
    END IF;

    -- Step 1: Check for unviewed feedback
    -- Find the most recent submission with feedback that hasn't been viewed
    SELECT s.id, s.task_id
    INTO v_submission_id, v_task_id
    FROM submission s
    JOIN all_mastery_tasks amt ON amt.id = s.task_id
    JOIN unit_section us ON us.id = amt.section_id
    JOIN learning_unit lu ON lu.id = us.learning_unit_id
    JOIN course_learning_unit_assignment cua ON cua.learning_unit_id = lu.id
    WHERE s.student_id = p_student_id
    AND cua.course_id = p_course_id
    AND s.feedback_viewed_at IS NULL
    AND (s.ai_feedback IS NOT NULL OR s.teacher_override_feedback IS NOT NULL)
    ORDER BY s.submitted_at DESC
    LIMIT 1;

    -- If unviewed feedback exists, return it with task details and mastery progress
    IF v_submission_id IS NOT NULL THEN
        SELECT json_build_object(
            'type', 'feedback',
            'submission_id', s.id,
            'task_id', s.task_id,
            'task_title', t.title,
            'task_instruction', t.instruction,
            'section_id', amt.section_id,
            'section_title', us.title,
            'unit_id', us.learning_unit_id,
            'unit_title', lu.title,
            'difficulty_level', amt.difficulty_level,
            'solution_hints', t.solution_hints,
            'submitted_at', s.submitted_at,
            'is_correct', s.is_correct,
            'submission_text', s.submission_text,
            'ai_feedback', s.ai_feedback,
            'ai_grade', s.ai_grade,
            'teacher_feedback', s.teacher_override_feedback,
            'teacher_grade', s.teacher_override_grade,
            'feed_back_text', s.feed_back_text,
            'feed_forward_text', s.feed_forward_text,
            -- Include mastery_progress
            'mastery_progress', CASE 
                WHEN smp.id IS NOT NULL THEN
                    json_build_object(
                        'stability', smp.stability,
                        'difficulty', smp.difficulty,
                        'retrievability', smp.retrievability,
                        'next_review_date', smp.next_review_date,
                        'last_review_date', smp.last_review_date,
                        'total_reviews', smp.total_reviews,
                        'successful_reviews', smp.successful_reviews
                    )
                ELSE NULL
            END
        ) INTO v_result
        FROM submission s
        JOIN all_mastery_tasks amt ON amt.id = s.task_id
        JOIN task_base t ON t.id = amt.id
        JOIN unit_section us ON us.id = amt.section_id
        JOIN learning_unit lu ON lu.id = us.learning_unit_id
        LEFT JOIN student_mastery_progress smp ON smp.task_id = s.task_id AND smp.student_id = p_student_id
        WHERE s.id = v_submission_id;
        
        RETURN v_result;
    END IF;

    -- Step 2: If no unviewed feedback, get next due mastery task
    -- Calculate priority for all mastery tasks
    WITH student_progress AS (
        SELECT 
            amt.id as task_id,
            MAX(s.submitted_at) as last_submission,
            COUNT(CASE WHEN s.is_correct THEN 1 END) as correct_count,
            COUNT(s.id) as total_attempts,
            smp.next_review_date,
            smp.stability,
            smp.retrievability,
            smp.difficulty,
            smp.last_review_date,
            smp.total_reviews,
            smp.successful_reviews
        FROM all_mastery_tasks amt
        JOIN unit_section us ON us.id = amt.section_id
        JOIN learning_unit lu ON lu.id = us.learning_unit_id
        JOIN course_learning_unit_assignment cua ON cua.learning_unit_id = lu.id
        LEFT JOIN submission s ON s.task_id = amt.id AND s.student_id = p_student_id
        LEFT JOIN student_mastery_progress smp ON smp.task_id = amt.id AND smp.student_id = p_student_id
        WHERE cua.course_id = p_course_id
        GROUP BY amt.id, smp.next_review_date, smp.stability, smp.retrievability, 
                 smp.difficulty, smp.last_review_date, smp.total_reviews, smp.successful_reviews
    ),
    prioritized_tasks AS (
        SELECT 
            sp.task_id,
            sp.last_submission,
            sp.correct_count,
            sp.total_attempts,
            sp.next_review_date,
            sp.stability,
            sp.retrievability,
            sp.difficulty,
            sp.last_review_date,
            sp.total_reviews,
            sp.successful_reviews,
            -- Priority calculation
            CASE
                -- Never attempted: highest priority
                WHEN sp.total_attempts = 0 THEN 1000
                -- Due for review (past next_review_date)
                WHEN sp.next_review_date IS NOT NULL AND sp.next_review_date <= CURRENT_TIMESTAMP THEN 
                    500 + EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - sp.next_review_date)) / 86400
                -- Has attempts but not yet due
                WHEN sp.next_review_date IS NOT NULL AND sp.next_review_date > CURRENT_TIMESTAMP THEN
                    100 - EXTRACT(EPOCH FROM (sp.next_review_date - CURRENT_TIMESTAMP)) / 86400
                -- Fallback for tasks with attempts but no review date
                ELSE 200
            END as priority_score
        FROM student_progress sp
    )
    SELECT json_build_object(
        'type', 'task',
        'task_id', amt.id,
        'task_title', t.title,
        'task_instruction', t.instruction,
        'section_id', amt.section_id,
        'section_title', us.title,
        'unit_id', us.learning_unit_id,
        'unit_title', lu.title,
        'difficulty_level', amt.difficulty_level,
        'solution_hints', t.solution_hints,
        'last_attempt', pt.last_submission,
        'correct_attempts', pt.correct_count,
        'total_attempts', pt.total_attempts,
        'next_review_date', pt.next_review_date,
        'priority_score', pt.priority_score,
        -- Include mastery_progress for proper display
        'mastery_progress', CASE 
            WHEN pt.stability IS NOT NULL THEN
                json_build_object(
                    'stability', pt.stability,
                    'difficulty', pt.difficulty,
                    'retrievability', pt.retrievability,
                    'next_review_date', pt.next_review_date,
                    'last_review_date', pt.last_review_date,
                    'total_reviews', pt.total_reviews,
                    'successful_reviews', pt.successful_reviews
                )
            ELSE NULL
        END
    ) INTO v_result
    FROM prioritized_tasks pt
    JOIN all_mastery_tasks amt ON amt.id = pt.task_id
    JOIN task_base t ON t.id = amt.id
    JOIN unit_section us ON us.id = amt.section_id
    JOIN learning_unit lu ON lu.id = us.learning_unit_id
    ORDER BY pt.priority_score DESC
    LIMIT 1;

    -- If no tasks found (edge case), return null
    IF v_result IS NULL THEN
        RETURN json_build_object(
            'type', 'no_tasks',
            'message', 'Keine weiteren Aufgaben verfuegbar'
        );
    END IF;

    RETURN v_result;
END;
$$;

-- Grant permissions
GRANT EXECUTE ON FUNCTION public.get_next_mastery_task_or_unviewed_feedback(TEXT, UUID, UUID) TO anon;

-- Update comment
COMMENT ON FUNCTION public.get_next_mastery_task_or_unviewed_feedback IS 'Returns either unviewed feedback (priority) or the next due mastery task for a student in a course, including mastery progress data for proper UI display.';