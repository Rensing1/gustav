-- Fix remaining functions with created_by -> creator_id references
-- Only fixing the SQL, keeping existing function signatures intact

-- Fix get_mastery_tasks_for_course (keeping the student_progress column)
DO $$
BEGIN
    -- Get the current function body and replace created_by with creator_id
    EXECUTE format('
        CREATE OR REPLACE FUNCTION public.get_mastery_tasks_for_course(
            p_session_id TEXT,
            p_course_id UUID
        )
        RETURNS TABLE (
            task_id UUID,
            task_title TEXT,
            section_id UUID,
            section_title TEXT,
            unit_id UUID,
            unit_title TEXT,
            difficulty_level INT,
            concept_explanation TEXT,
            student_progress JSONB
        )
        SECURITY DEFINER
        SET search_path = public
        LANGUAGE plpgsql AS $func$
        DECLARE
            v_user_id UUID;
            v_user_role TEXT;
            v_is_valid BOOLEAN;
        BEGIN
            -- Session validation
            SELECT user_id, user_role, is_valid
            INTO v_user_id, v_user_role, v_is_valid
            FROM public.validate_session_and_get_user(p_session_id);

            IF NOT v_is_valid OR v_user_role != ''teacher'' THEN
                RAISE EXCEPTION ''Unauthorized: Only teachers can view mastery tasks for course'';
            END IF;

            -- Check if teacher is authorized for this course (FIX: created_by -> creator_id)
            IF NOT EXISTS (
                SELECT 1 FROM course_teacher 
                WHERE teacher_id = v_user_id AND course_id = p_course_id
            ) AND NOT EXISTS (
                SELECT 1 FROM course 
                WHERE id = p_course_id AND creator_id = v_user_id
            ) THEN
                RAISE EXCEPTION ''Unauthorized: Teacher not authorized for this course'';
            END IF;

            -- Get mastery tasks with student progress
            RETURN QUERY
            WITH course_students AS (
                SELECT student_id 
                FROM course_student 
                WHERE course_id = p_course_id
            ),
            task_progress AS (
                SELECT 
                    mt.id as task_id,
                    jsonb_object_agg(
                        cs.student_id::TEXT,
                        COALESCE(
                            jsonb_build_object(
                                ''completed'', EXISTS(
                                    SELECT 1 FROM mastery_submission ms
                                    WHERE ms.task_id = mt.id 
                                    AND ms.student_id = cs.student_id
                                    AND ms.final_score >= 0.8
                                ),
                                ''attempts'', (
                                    SELECT COUNT(*) 
                                    FROM mastery_submission ms
                                    WHERE ms.task_id = mt.id 
                                    AND ms.student_id = cs.student_id
                                ),
                                ''best_score'', (
                                    SELECT MAX(final_score) 
                                    FROM mastery_submission ms
                                    WHERE ms.task_id = mt.id 
                                    AND ms.student_id = cs.student_id
                                )
                            ),
                            ''{}''::jsonb
                        )
                    ) as progress
                FROM mastery_task mt
                CROSS JOIN course_students cs
                GROUP BY mt.id
            )
            SELECT 
                mt.id as task_id,
                mt.title as task_title,
                s.id as section_id,
                s.title as section_title,
                lu.id as unit_id,
                lu.title as unit_title,
                mt.difficulty_level,
                mt.concept_explanation,
                COALESCE(tp.progress, ''{}''::jsonb) as student_progress
            FROM mastery_task mt
            JOIN unit_section s ON s.id = mt.section_id
            JOIN learning_unit lu ON lu.id = s.learning_unit_id
            LEFT JOIN task_progress tp ON tp.task_id = mt.id
            WHERE EXISTS (
                SELECT 1 
                FROM course_learning_unit_assignment cua
                WHERE cua.course_id = p_course_id 
                AND cua.learning_unit_id = lu.id
            )
            ORDER BY lu.title, s.order_in_unit, mt.difficulty_level;
        END;
        $func$
    ');
END $$;