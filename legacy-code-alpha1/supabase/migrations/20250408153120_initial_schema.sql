-- 1. Define ENUM types
CREATE TYPE user_role AS ENUM ('student', 'teacher');

-- 2. Create profiles table
CREATE TABLE profiles (
    id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE, -- Verknüpfung mit Supabase Auth User
    role user_role NOT NULL,
    full_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Index for faster role filtering
CREATE INDEX idx_profiles_role ON profiles(role);
-- RLS policy will be added in a separate migration/step

-- 3. Create course table
CREATE TABLE course (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    creator_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE SET NULL, -- Lehrer-ID, bei Löschen des Lehrers wird die ID auf NULL gesetzt
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Index for faster lookup by creator
CREATE INDEX idx_course_creator_id ON course(creator_id);

-- 4. Create course_teacher junction table (M:N)
CREATE TABLE course_teacher (
    course_id uuid NOT NULL REFERENCES course(id) ON DELETE CASCADE,
    teacher_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (course_id, teacher_id) -- Composite Primary Key
);
-- Indexes for faster joins/lookups
CREATE INDEX idx_course_teacher_teacher_id ON course_teacher(teacher_id);
-- CREATE INDEX idx_course_teacher_course_id ON course_teacher(course_id); -- Bereits Teil des PK

-- 5. Create course_student junction table (M:N)
CREATE TABLE course_student (
    course_id uuid NOT NULL REFERENCES course(id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (course_id, student_id) -- Composite Primary Key
);
-- Indexes for faster joins/lookups
CREATE INDEX idx_course_student_student_id ON course_student(student_id);
-- CREATE INDEX idx_course_student_course_id ON course_student(course_id); -- Bereits Teil des PK

-- 6. Create learning_unit table
CREATE TABLE learning_unit (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT,
    creator_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE SET NULL, -- Lehrer-ID
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Index for faster lookup by creator
CREATE INDEX idx_learning_unit_creator_id ON learning_unit(creator_id);

-- 7. Create course_learning_unit junction table (M:N + publishing)
CREATE TABLE course_learning_unit (
    course_id uuid NOT NULL REFERENCES course(id) ON DELETE CASCADE,
    unit_id uuid NOT NULL REFERENCES learning_unit(id) ON DELETE CASCADE,
    is_published BOOLEAN NOT NULL DEFAULT false,
    published_at TIMESTAMPTZ,
    PRIMARY KEY (course_id, unit_id) -- Composite Primary Key
);
-- Indexes for faster joins/lookups
CREATE INDEX idx_course_learning_unit_unit_id ON course_learning_unit(unit_id);
-- CREATE INDEX idx_course_learning_unit_course_id ON course_learning_unit(course_id); -- Bereits Teil des PK
CREATE INDEX idx_course_learning_unit_published ON course_learning_unit(is_published); -- Für schnelle Filterung veröffentlichter Einheiten

-- 8. Create task table
CREATE TABLE task (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_id uuid NOT NULL REFERENCES learning_unit(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    instruction TEXT NOT NULL,
    task_type TEXT NOT NULL, -- z.B. 'text', 'multiple_choice', 'file_upload'
    learning_material JSONB,
    order_in_unit INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Index for faster lookup by unit
CREATE INDEX idx_task_unit_id ON task(unit_id);

-- 9. Create submission table
CREATE TABLE submission (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    task_id uuid NOT NULL REFERENCES task(id) ON DELETE CASCADE,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    solution_data JSONB NOT NULL,
    ai_feedback TEXT,
    ai_grade TEXT, -- Flexibler als NUMERIC für Start
    feedback_generated_at TIMESTAMPTZ,
    grade_generated_at TIMESTAMPTZ,
    teacher_override_feedback TEXT,
    teacher_override_grade TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT unique_student_task_submission UNIQUE (student_id, task_id) -- Verhindert Mehrfacheinreichung
);
-- Indexes for faster lookups
CREATE INDEX idx_submission_student_id ON submission(student_id);
CREATE INDEX idx_submission_task_id ON submission(task_id);

-- 10. Optional: Trigger function to automatically update 'updated_at' timestamps
-- Supabase projects often come with this pre-configured via the 'moddatetime' extension.
-- If not, or for clarity, you can add it:
--
-- CREATE OR REPLACE FUNCTION public.handle_updated_at()
-- RETURNS TRIGGER AS $$
-- BEGIN
--   NEW.updated_at = now();
--   RETURN NEW;
-- END;
-- $$ LANGUAGE plpgsql;
--
-- CREATE TRIGGER on_profile_update BEFORE UPDATE ON profiles FOR EACH ROW EXECUTE PROCEDURE public.handle_updated_at();
-- CREATE TRIGGER on_course_update BEFORE UPDATE ON course FOR EACH ROW EXECUTE PROCEDURE public.handle_updated_at();
-- CREATE TRIGGER on_learning_unit_update BEFORE UPDATE ON learning_unit FOR EACH ROW EXECUTE PROCEDURE public.handle_updated_at();
-- CREATE TRIGGER on_task_update BEFORE UPDATE ON task FOR EACH ROW EXECUTE PROCEDURE public.handle_updated_at();
-- CREATE TRIGGER on_submission_update BEFORE UPDATE ON submission FOR EACH ROW EXECUTE PROCEDURE public.handle_updated_at();

-- Grant usage permissions for the new schemas/types to standard roles
-- (Supabase handles basic grants, but explicit grants can be clearer)
GRANT usage ON SCHEMA public TO anon, authenticated;
GRANT select ON ALL TABLES IN SCHEMA public TO anon, authenticated;
-- More specific grants will be handled by RLS policies.

-- Grant permissions on the ENUM type
GRANT usage ON TYPE public.user_role TO anon, authenticated;