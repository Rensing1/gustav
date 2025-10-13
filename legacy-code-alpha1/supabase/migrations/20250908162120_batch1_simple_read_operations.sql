-- Batch 1: Simple READ Operations (10 Functions)
-- PostgreSQL Functions Migration fuer HttpOnly Cookie Support

-- 1. get_users_by_role
CREATE OR REPLACE FUNCTION public.get_users_by_role(
    p_session_id TEXT,
    p_role TEXT
)
RETURNS TABLE(
    id UUID,
    email TEXT,
    display_name TEXT,
    role TEXT
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Nur Lehrer duerfen andere User sehen
    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RETURN;
    END IF;

    -- User mit spezifischer Rolle zurueckgeben
    RETURN QUERY
    SELECT
        p.id,
        p.email,
        p.display_name,
        p.role
    FROM profiles p
    WHERE p.role = p_role
    ORDER BY p.display_name, p.email;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_users_by_role TO anon;

-- 2. get_students_in_course
CREATE OR REPLACE FUNCTION public.get_students_in_course(
    p_session_id TEXT,
    p_course_id UUID
)
RETURNS TABLE(
    id UUID,
    email TEXT,
    display_name TEXT,
    role TEXT,
    course_id UUID
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Berechtigung pruefen: Lehrer des Kurses oder Student im Kurs
    IF v_user_role = 'teacher' THEN
        -- Lehrer muss Ersteller oder zugewiesen sein
        IF NOT EXISTS (
            SELECT 1 FROM course c 
            WHERE c.id = p_course_id AND c.creator_id = v_user_id
        ) AND NOT EXISTS (
            SELECT 1 FROM course_teacher ct
            WHERE ct.course_id = p_course_id AND ct.teacher_id = v_user_id
        ) THEN
            RETURN;
        END IF;
    ELSIF v_user_role = 'student' THEN
        -- Student muss im Kurs sein
        IF NOT EXISTS (
            SELECT 1 FROM course_student cs
            WHERE cs.course_id = p_course_id AND cs.student_id = v_user_id
        ) THEN
            RETURN;
        END IF;
    END IF;

    -- Studenten im Kurs zurueckgeben
    RETURN QUERY
    SELECT
        p.id,
        p.email,
        p.display_name,
        p.role,
        cs.course_id
    FROM course_student cs
    JOIN profiles p ON p.id = cs.student_id
    WHERE cs.course_id = p_course_id
    ORDER BY p.display_name, p.email;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_students_in_course TO anon;

-- 3. get_teachers_in_course
CREATE OR REPLACE FUNCTION public.get_teachers_in_course(
    p_session_id TEXT,
    p_course_id UUID
)
RETURNS TABLE(
    id UUID,
    email TEXT,
    display_name TEXT,
    role TEXT,
    course_id UUID
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Berechtigung pruefen (wie bei get_students_in_course)
    IF v_user_role = 'teacher' THEN
        IF NOT EXISTS (
            SELECT 1 FROM course c 
            WHERE c.id = p_course_id AND c.creator_id = v_user_id
        ) AND NOT EXISTS (
            SELECT 1 FROM course_teacher ct
            WHERE ct.course_id = p_course_id AND ct.teacher_id = v_user_id
        ) THEN
            RETURN;
        END IF;
    ELSIF v_user_role = 'student' THEN
        IF NOT EXISTS (
            SELECT 1 FROM course_student cs
            WHERE cs.course_id = p_course_id AND cs.student_id = v_user_id
        ) THEN
            RETURN;
        END IF;
    END IF;

    -- Lehrer im Kurs zurueckgeben (inkl. Ersteller)
    RETURN QUERY
    SELECT
        p.id,
        p.email,
        p.display_name,
        p.role,
        c.id as course_id
    FROM course c
    JOIN profiles p ON p.id = c.creator_id
    WHERE c.id = p_course_id
    UNION
    SELECT
        p.id,
        p.email,
        p.display_name,
        p.role,
        ct.course_id
    FROM course_teacher ct
    JOIN profiles p ON p.id = ct.teacher_id
    WHERE ct.course_id = p_course_id
    ORDER BY display_name, email;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_teachers_in_course TO anon;

-- 4. get_courses_assigned_to_unit
CREATE OR REPLACE FUNCTION public.get_courses_assigned_to_unit(
    p_session_id TEXT,
    p_unit_id UUID
)
RETURNS TABLE(
    id UUID,
    name TEXT,
    creator_id UUID,
    created_at TIMESTAMPTZ
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Nur Lehrer duerfen diese Funktion nutzen
    IF v_user_role != 'teacher' THEN
        RETURN;
    END IF;

    -- Kurse zurueckgeben, denen diese Unit zugewiesen ist
    RETURN QUERY
    SELECT
        c.id,
        c.name,
        c.creator_id,
        c.created_at
    FROM course c
    JOIN course_learning_unit_assignment clua ON clua.course_id = c.id
    WHERE clua.learning_unit_id = p_unit_id
    ORDER BY c.name;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_courses_assigned_to_unit TO anon;

-- 5. get_user_course_ids
CREATE OR REPLACE FUNCTION public.get_user_course_ids(
    p_session_id TEXT,
    p_student_id UUID
)
RETURNS TABLE(
    course_id UUID
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Benutzer kann nur eigene Kurse sehen, Lehrer kuennen alle sehen
    IF v_user_role = 'student' AND v_user_id != p_student_id THEN
        RETURN;
    END IF;

    -- Kurs-IDs zurueckgeben
    RETURN QUERY
    SELECT cs.course_id
    FROM course_student cs
    WHERE cs.student_id = p_student_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_user_course_ids TO anon;

-- 6. get_student_courses
CREATE OR REPLACE FUNCTION public.get_student_courses(
    p_session_id TEXT,
    p_student_id UUID
)
RETURNS TABLE(
    id UUID,
    name TEXT,
    creator_id UUID,
    created_at TIMESTAMPTZ
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Benutzer kann nur eigene Kurse sehen, Lehrer kuennen alle sehen
    IF v_user_role = 'student' AND v_user_id != p_student_id THEN
        RETURN;
    END IF;

    -- Kurse des Studenten zurueckgeben
    RETURN QUERY
    SELECT
        c.id,
        c.name,
        c.creator_id,
        c.created_at
    FROM course c
    JOIN course_student cs ON cs.course_id = c.id
    WHERE cs.student_id = p_student_id
    ORDER BY c.created_at DESC;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_student_courses TO anon;

-- 7. get_course_by_id
CREATE OR REPLACE FUNCTION public.get_course_by_id(
    p_session_id TEXT,
    p_course_id UUID
)
RETURNS TABLE(
    id UUID,
    name TEXT,
    creator_id UUID,
    created_at TIMESTAMPTZ
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Berechtigung pruefen: User muss im Kurs sein oder Lehrer
    IF v_user_role = 'student' THEN
        IF NOT EXISTS (
            SELECT 1 FROM course_student cs
            WHERE cs.course_id = p_course_id AND cs.student_id = v_user_id
        ) THEN
            RETURN;
        END IF;
    ELSIF v_user_role = 'teacher' THEN
        -- Lehrer kuennen alle Kurse sehen (fuer Admin-Funktionen)
        NULL; -- Explizit keine Einschruenkung
    END IF;

    -- Kurs zurueckgeben
    RETURN QUERY
    SELECT
        c.id,
        c.name,
        c.creator_id,
        c.created_at
    FROM course c
    WHERE c.id = p_course_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_course_by_id TO anon;

-- 8. get_submission_by_id
CREATE OR REPLACE FUNCTION public.get_submission_by_id(
    p_session_id TEXT,
    p_submission_id UUID
)
RETURNS TABLE(
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
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Berechtigung pruefen: Student kann nur eigene, Lehrer alle
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
    WHERE s.id = p_submission_id
    AND (
        v_user_role = 'teacher' 
        OR s.student_id = v_user_id
    );
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_submission_by_id TO anon;

-- 9. get_submission_history
CREATE OR REPLACE FUNCTION public.get_submission_history(
    p_session_id TEXT,
    p_student_id UUID,
    p_task_id UUID
)
RETURNS TABLE(
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
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Berechtigung pruefen
    IF v_user_role = 'student' AND v_user_id != p_student_id THEN
        RETURN;
    END IF;

    -- Submission-Historie zurueckgeben
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
    ORDER BY s.submitted_at DESC;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_submission_history TO anon;

-- 10. get_all_feedback
CREATE OR REPLACE FUNCTION public.get_all_feedback(
    p_session_id TEXT
)
RETURNS TABLE(
    id UUID,
    page_identifier TEXT,
    feedback_type TEXT,
    feedback_text TEXT,
    sentiment TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Nur Lehrer duerfen Feedback sehen
    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RETURN;
    END IF;

    -- Alles Feedback zurueckgeben
    RETURN QUERY
    SELECT
        f.id,
        f.page_identifier,
        f.feedback_type,
        f.feedback_text,
        f.sentiment,
        f.metadata,
        f.created_at
    FROM feedback f
    ORDER BY f.created_at DESC;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_all_feedback TO anon;