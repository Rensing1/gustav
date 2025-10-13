-- Fix mastery_tasks schema and remaining feedback issues
-- Issues addressed:
-- 1. mastery_tasks missing spaced_repetition_interval column
-- 2. feedback missing sentiment column
-- 3. Function signature issues

-- Add missing columns to mastery_tasks table
ALTER TABLE mastery_tasks 
ADD COLUMN IF NOT EXISTS spaced_repetition_interval INTEGER DEFAULT 1;

-- Add missing columns to feedback table 
ALTER TABLE feedback 
ADD COLUMN IF NOT EXISTS sentiment TEXT,
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- Update the function signature problem: get_published_section_details_for_student
-- The error shows it's looking for (p_course_id, p_session_id, p_student_id, p_unit_id) 
-- but the function exists with (p_session_id, p_student_id, p_unit_id, p_course_id)

-- Drop the existing function and recreate with correct parameter order
DROP FUNCTION IF EXISTS public.get_published_section_details_for_student(TEXT, UUID, UUID, UUID);

-- Create function with parameter order that matches the Python code calls
CREATE OR REPLACE FUNCTION public.get_published_section_details_for_student(
    p_session_id TEXT,
    p_course_id UUID,
    p_student_id UUID, 
    p_unit_id UUID
)
RETURNS TABLE (
    section_id UUID,
    section_title TEXT,
    section_description TEXT,
    section_materials JSONB,
    order_in_unit INT,
    is_published BOOLEAN,
    tasks JSONB
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

    -- Check permissions: student must be self, teacher can see all
    IF v_user_role = 'student' AND v_user_id != p_student_id THEN
        RETURN;
    END IF;

    -- Complex query to get section details with tasks and submission status
    RETURN QUERY
    WITH published_sections AS (
        SELECT 
            s.id,
            s.title,
            COALESCE(s.title, '') as description,  -- Use title as description if no description field
            s.materials,
            s.order_in_unit,
            COALESCE(cuss.is_published, FALSE) as is_published
        FROM unit_section s
        LEFT JOIN course_unit_section_status cuss ON 
            cuss.section_id = s.id AND 
            cuss.course_id = p_course_id
        WHERE s.unit_id = p_unit_id
    ),
    task_details AS (
        -- Get regular tasks with submission info
        SELECT 
            t.section_id,
            jsonb_build_object(
                'id', t.id,
                'title', t.title,
                'task_type', t.task_type,
                'order_in_section', COALESCE(rt.order_in_section, 0),
                'is_mastery', FALSE,
                'max_attempts', COALESCE(rt.max_attempts, 1),
                'prompt', COALESCE(rt.prompt, ''),
                'submission_count', COUNT(sub.id),
                'attempts_remaining', GREATEST(0, COALESCE(rt.max_attempts, 1) - COUNT(sub.id)),
                'latest_submission', 
                CASE 
                    WHEN COUNT(sub.id) > 0 THEN
                        jsonb_build_object(
                            'id', MAX(sub.id),
                            'is_correct', BOOL_OR(sub.is_correct),
                            'submitted_at', MAX(sub.submitted_at),
                            'has_feedback', MAX(sub.ai_feedback) IS NOT NULL OR MAX(sub.teacher_override_feedback) IS NOT NULL,
                            'feedback_viewed', MAX(sub.feedback_viewed_at) IS NOT NULL
                        )
                    ELSE NULL
                END
            ) as task_data
        FROM task_base t
        LEFT JOIN regular_tasks rt ON rt.task_id = t.id
        LEFT JOIN submission sub ON 
            sub.task_id = t.id AND 
            sub.student_id = p_student_id
        WHERE t.task_type = 'regular'
        GROUP BY t.id, t.section_id, t.title, t.task_type, rt.order_in_section, rt.max_attempts, rt.prompt

        UNION ALL

        -- Get mastery tasks
        SELECT 
            t.section_id,
            jsonb_build_object(
                'id', t.id,
                'title', t.title,
                'task_type', t.task_type,
                'order_in_section', 999, -- Put mastery tasks at end
                'is_mastery', TRUE,
                'max_attempts', 999,
                'prompt', COALESCE(mt.prompt, ''),
                'difficulty_level', COALESCE(mt.difficulty_level, 1),
                'concept_explanation', COALESCE(mt.concept_explanation, '')
            ) as task_data
        FROM task_base t
        JOIN mastery_tasks mt ON mt.task_id = t.id
        WHERE t.task_type = 'mastery'
    )
    SELECT 
        ps.id as section_id,
        ps.title as section_title,
        ps.description as section_description,
        ps.materials as section_materials,
        ps.order_in_unit,
        ps.is_published,
        COALESCE(
            jsonb_agg(
                td.task_data 
                ORDER BY (td.task_data->>'order_in_section')::INT
            ) FILTER (WHERE td.task_data IS NOT NULL),
            '[]'::jsonb
        ) as tasks
    FROM published_sections ps
    LEFT JOIN task_details td ON td.section_id = ps.id
    WHERE ps.is_published = TRUE OR v_user_role = 'teacher'
    GROUP BY ps.id, ps.title, ps.description, ps.materials, ps.order_in_unit, ps.is_published
    ORDER BY ps.order_in_unit;
END;
$$;