-- Batch 4: Submission System
-- 10 Functions for Submission Creation, Reading and Management
-- Complex validation, attempt counting, and feedback handling

-- 1. create_submission - Creates a new submission with complex validation
CREATE OR REPLACE FUNCTION public.create_submission(
    p_session_id TEXT,
    p_task_id UUID,
    p_submission_text TEXT
)
RETURNS UUID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_submission_id UUID;
    v_attempt_count INT;
    v_max_attempts INT;
    v_is_mastery BOOLEAN;
    v_section_id UUID;
    v_course_id UUID;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'student' THEN
        RAISE EXCEPTION 'Unauthorized: Only students can create submissions';
    END IF;

    -- Check if task exists in regular tasks
    SELECT 
        t.section_id,
        t.max_attempts,
        FALSE
    INTO v_section_id, v_max_attempts, v_is_mastery
    FROM all_regular_tasks t
    WHERE t.id = p_task_id;

    -- If not found, check mastery tasks
    IF NOT FOUND THEN
        SELECT 
            t.section_id,
            NULL::INT, -- Mastery tasks have unlimited attempts
            TRUE
        INTO v_section_id, v_max_attempts, v_is_mastery
        FROM all_mastery_tasks t
        WHERE t.id = p_task_id;
        
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Task not found';
        END IF;
    END IF;

    -- Get course_id for this task
    SELECT cua.course_id
    INTO v_course_id
    FROM unit_section s
    JOIN learning_unit lu ON lu.id = s.learning_unit_id
    JOIN course_learning_unit_assignment cua ON cua.learning_unit_id = lu.id
    WHERE s.id = v_section_id
    LIMIT 1;

    -- Check if student is enrolled in the course
    IF NOT EXISTS (
        SELECT 1 FROM course_student cs
        WHERE cs.student_id = v_user_id AND cs.course_id = v_course_id
    ) THEN
        RAISE EXCEPTION 'Student not enrolled in course';
    END IF;

    -- Check attempt limit for regular tasks
    IF NOT v_is_mastery AND v_max_attempts IS NOT NULL THEN
        SELECT COUNT(*)
        INTO v_attempt_count
        FROM submission s
        WHERE s.student_id = v_user_id AND s.task_id = p_task_id;

        IF v_attempt_count >= v_max_attempts THEN
            RAISE EXCEPTION 'Maximum attempts reached';
        END IF;
    END IF;

    -- Create submission
    INSERT INTO submission (
        student_id,
        task_id,
        submission_text,
        is_correct,
        submitted_at
    )
    VALUES (
        v_user_id,
        p_task_id,
        p_submission_text,
        FALSE, -- Default to false, will be updated by AI
        NOW()
    )
    RETURNING id INTO v_submission_id;

    RETURN v_submission_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.create_submission TO anon;

-- 2. get_submission_for_task - Gets the latest submission for a task
CREATE OR REPLACE FUNCTION public.get_submission_for_task(
    p_session_id TEXT,
    p_student_id UUID,
    p_task_id UUID
)
RETURNS TABLE (
    id UUID,
    student_id UUID,
    task_id UUID,
    submission_text TEXT,
    is_correct BOOLEAN,
    submitted_at TIMESTAMPTZ,
    ai_feedback TEXT,
    ai_feedback_generated_at TIMESTAMPTZ,
    teacher_feedback TEXT,
    teacher_feedback_generated_at TIMESTAMPTZ,
    override_grade BOOLEAN,
    feedback_viewed_at TIMESTAMPTZ
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
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
        RETURN;
    END IF;

    -- Check permissions: student can see own, teacher can see all
    IF v_user_role = 'student' AND v_user_id != p_student_id THEN
        RETURN;
    END IF;

    -- Return latest submission
    RETURN QUERY
    SELECT 
        s.id,
        s.student_id,
        s.task_id,
        s.submission_text,
        s.is_correct,
        s.submitted_at,
        s.ai_feedback,
        s.ai_feedback_generated_at,
        s.teacher_feedback,
        s.teacher_feedback_generated_at,
        s.override_grade,
        s.feedback_viewed_at
    FROM submission s
    WHERE s.student_id = p_student_id
    AND s.task_id = p_task_id
    ORDER BY s.submitted_at DESC
    LIMIT 1;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_submission_for_task TO anon;

-- 3. get_remaining_attempts - Calculates remaining attempts for a regular task
CREATE OR REPLACE FUNCTION public.get_remaining_attempts(
    p_session_id TEXT,
    p_student_id UUID,
    p_task_id UUID
)
RETURNS INT
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_max_attempts INT;
    v_attempt_count INT;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN NULL;
    END IF;

    -- Check permissions
    IF v_user_role = 'student' AND v_user_id != p_student_id THEN
        RETURN NULL;
    END IF;

    -- Get max attempts for regular task
    SELECT max_attempts
    INTO v_max_attempts
    FROM all_regular_tasks
    WHERE id = p_task_id;

    IF NOT FOUND THEN
        -- Mastery tasks have unlimited attempts
        RETURN NULL;
    END IF;

    -- Count existing attempts
    SELECT COUNT(*)
    INTO v_attempt_count
    FROM submission s
    WHERE s.student_id = p_student_id AND s.task_id = p_task_id;

    -- Return remaining attempts
    RETURN GREATEST(0, v_max_attempts - v_attempt_count);
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_remaining_attempts TO anon;

-- 4. get_task_details - Gets task details, trying regular first then mastery
CREATE OR REPLACE FUNCTION public.get_task_details(
    p_session_id TEXT,
    p_task_id UUID
)
RETURNS TABLE (
    id UUID,
    section_id UUID,
    title TEXT,
    task_type TEXT,
    order_in_section INT,
    created_at TIMESTAMPTZ,
    prompt TEXT,
    is_mastery BOOLEAN,
    max_attempts INT,
    grading_criteria TEXT[],
    difficulty_level INT,
    concept_explanation TEXT
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
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
        RETURN;
    END IF;

    -- Try to get from regular tasks first
    RETURN QUERY
    SELECT 
        t.id,
        t.section_id,
        t.title,
        t.task_type,
        t.order_in_section,
        t.created_at,
        t.prompt,
        t.is_mastery,
        t.max_attempts,
        t.grading_criteria,
        NULL::INT as difficulty_level,
        NULL::TEXT as concept_explanation
    FROM all_regular_tasks t
    WHERE t.id = p_task_id;

    -- If not found, try mastery tasks
    IF NOT FOUND THEN
        RETURN QUERY
        SELECT 
            t.id,
            t.section_id,
            t.title,
            t.task_type,
            t.order_in_section,
            t.created_at,
            t.prompt,
            t.is_mastery,
            NULL::INT as max_attempts,
            NULL::TEXT[] as grading_criteria,
            t.difficulty_level,
            t.concept_explanation
        FROM all_mastery_tasks t
        WHERE t.id = p_task_id;
    END IF;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_task_details TO anon;

-- 5. update_submission_ai_results - Updates submission with AI grading results
CREATE OR REPLACE FUNCTION public.update_submission_ai_results(
    p_session_id TEXT,
    p_submission_id UUID,
    p_is_correct BOOLEAN,
    p_ai_feedback TEXT
)
RETURNS VOID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
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
        RAISE EXCEPTION 'Unauthorized: Invalid session';
    END IF;

    -- This function should be called by the system after AI processing
    -- For now, we allow both students (for their own) and teachers
    IF v_user_role = 'student' THEN
        -- Verify student owns the submission
        IF NOT EXISTS (
            SELECT 1 FROM submission s
            WHERE s.id = p_submission_id AND s.student_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Unauthorized: Student does not own submission';
        END IF;
    END IF;

    -- Update submission
    UPDATE submission
    SET 
        is_correct = p_is_correct,
        ai_feedback = p_ai_feedback,
        ai_feedback_generated_at = NOW()
    WHERE id = p_submission_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.update_submission_ai_results TO anon;

-- 6. update_submission_teacher_override - Teacher can override grade and add feedback
CREATE OR REPLACE FUNCTION public.update_submission_teacher_override(
    p_session_id TEXT,
    p_submission_id UUID,
    p_override_grade BOOLEAN,
    p_teacher_feedback TEXT
)
RETURNS VOID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_student_id UUID;
    v_task_id UUID;
    v_course_id UUID;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can override grades';
    END IF;

    -- Get submission info
    SELECT s.student_id, s.task_id
    INTO v_student_id, v_task_id
    FROM submission s
    WHERE s.id = p_submission_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Submission not found';
    END IF;

    -- Check if teacher has access to this course
    SELECT cua.course_id
    INTO v_course_id
    FROM task_base t
    JOIN unit_section sec ON sec.id = t.section_id
    JOIN learning_unit lu ON lu.id = sec.learning_unit_id
    JOIN course_learning_unit_assignment cua ON cua.learning_unit_id = lu.id
    WHERE t.id = v_task_id
    LIMIT 1;

    IF NOT EXISTS (
        SELECT 1 FROM course_teacher ct
        WHERE ct.teacher_id = v_user_id AND ct.course_id = v_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course c
        WHERE c.id = v_course_id AND c.created_by = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Update submission
    UPDATE submission
    SET 
        override_grade = p_override_grade,
        teacher_feedback = p_teacher_feedback,
        teacher_feedback_generated_at = NOW()
    WHERE id = p_submission_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.update_submission_teacher_override TO anon;

-- 7. mark_feedback_as_viewed_safe - Marks feedback as viewed
CREATE OR REPLACE FUNCTION public.mark_feedback_as_viewed_safe(
    p_session_id TEXT,
    p_submission_id UUID
)
RETURNS VOID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
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
        RAISE EXCEPTION 'Unauthorized: Invalid session';
    END IF;

    -- Only students can mark their own feedback as viewed
    IF v_user_role != 'student' THEN
        RETURN;
    END IF;

    -- Update only if student owns the submission
    UPDATE submission
    SET feedback_viewed_at = NOW()
    WHERE id = p_submission_id 
    AND student_id = v_user_id
    AND feedback_viewed_at IS NULL;
END;
$$;

GRANT EXECUTE ON FUNCTION public.mark_feedback_as_viewed_safe TO anon;

-- 8. save_mastery_submission - Saves a mastery-specific submission
CREATE OR REPLACE FUNCTION public.save_mastery_submission(
    p_session_id TEXT,
    p_task_id UUID,
    p_submission_id UUID,
    p_is_correct BOOLEAN,
    p_time_spent_seconds INT
)
RETURNS VOID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'student' THEN
        RAISE EXCEPTION 'Unauthorized: Only students can save mastery submissions';
    END IF;

    -- Verify task is a mastery task
    IF NOT EXISTS (
        SELECT 1 FROM all_mastery_tasks t
        WHERE t.id = p_task_id
    ) THEN
        RAISE EXCEPTION 'Task is not a mastery task';
    END IF;

    -- Verify student owns the submission
    IF NOT EXISTS (
        SELECT 1 FROM submission s
        WHERE s.id = p_submission_id AND s.student_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Student does not own submission';
    END IF;

    -- Insert or update mastery submission record
    INSERT INTO mastery_submission (
        submission_id,
        time_spent_seconds,
        created_at
    )
    VALUES (
        p_submission_id,
        p_time_spent_seconds,
        NOW()
    )
    ON CONFLICT (submission_id) 
    DO UPDATE SET
        time_spent_seconds = EXCLUDED.time_spent_seconds;

    -- Update submission correctness
    UPDATE submission
    SET is_correct = p_is_correct
    WHERE id = p_submission_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.save_mastery_submission TO anon;

-- 9. submit_feedback - Allows anonymous feedback submission
CREATE OR REPLACE FUNCTION public.submit_feedback(
    p_session_id TEXT,
    p_page_identifier TEXT,
    p_feedback_type TEXT,
    p_feedback_text TEXT,
    p_sentiment TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT NULL
)
RETURNS UUID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_feedback_id UUID;
BEGIN
    -- Session validation (but allow anonymous feedback)
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Insert feedback (anonymous allowed)
    INSERT INTO feedback (
        page_identifier,
        feedback_type,
        feedback_text,
        sentiment,
        metadata,
        created_at
    )
    VALUES (
        p_page_identifier,
        p_feedback_type,
        p_feedback_text,
        p_sentiment,
        p_metadata,
        NOW()
    )
    RETURNING id INTO v_feedback_id;

    RETURN v_feedback_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.submit_feedback TO anon;

-- 10. calculate_learning_streak - Calculates consecutive learning days
CREATE OR REPLACE FUNCTION public.calculate_learning_streak(
    p_session_id TEXT,
    p_student_id UUID
)
RETURNS INT
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_streak INT := 0;
    v_last_date DATE;
    v_current_date DATE;
    v_submission_date DATE;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN 0;
    END IF;

    -- Check permissions
    IF v_user_role = 'student' AND v_user_id != p_student_id THEN
        RETURN 0;
    END IF;

    -- Get today's date
    v_current_date := CURRENT_DATE;
    v_last_date := v_current_date;

    -- Calculate streak by checking consecutive days with submissions
    FOR v_submission_date IN
        SELECT DISTINCT DATE(submitted_at) as submission_date
        FROM submission
        WHERE student_id = p_student_id
        ORDER BY submission_date DESC
    LOOP
        -- If this date is today or consecutive to last date, increment streak
        IF v_submission_date = v_last_date OR 
           v_submission_date = v_last_date - INTERVAL '1 day' THEN
            v_streak := v_streak + 1;
            v_last_date := v_submission_date;
        ELSE
            -- Streak broken
            EXIT;
        END IF;
    END LOOP;

    RETURN v_streak;
END;
$$;

GRANT EXECUTE ON FUNCTION public.calculate_learning_streak TO anon;