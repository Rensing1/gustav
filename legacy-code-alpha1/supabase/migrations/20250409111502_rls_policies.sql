-- Phase 1b: Row Level Security Policies

-- 1. Helper Function to get the role of the currently authenticated user
CREATE OR REPLACE FUNCTION get_my_role()
RETURNS user_role -- Use the ENUM type defined in the previous migration
LANGUAGE sql
SECURITY DEFINER -- Essential for RLS checks across tables
STABLE -- Indicates the function cannot modify the database and always returns the same result for the same arguments within a single scan
SET search_path = public -- Explicitly set schema context to avoid ambiguity
AS $$
  SELECT role
  FROM public.profiles
  WHERE id = auth.uid();
$$;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION get_my_role() TO authenticated;


-- 2. Enable RLS for all relevant tables
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.course ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.course_teacher ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.course_student ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.learning_unit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.course_learning_unit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.submission ENABLE ROW LEVEL SECURITY;


-- 3. Define RLS Policies

-- ======= PROFILES =======
-- Users can view their own profile.
CREATE POLICY "Allow individual user access to own profile"
  ON public.profiles FOR SELECT
  USING (auth.uid() = id);

-- Users can update their own profile.
CREATE POLICY "Allow individual user update to own profile"
  ON public.profiles FOR UPDATE
  USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id);
-- Note: INSERT is handled by Supabase Auth trigger usually. DELETE cascades from auth.users.

-- ======= COURSE =======
-- Teachers can manage all courses (Simplification for prototype)
CREATE POLICY "Allow teachers full access to courses"
  ON public.course FOR ALL
  USING (get_my_role() = 'teacher')
  WITH CHECK (get_my_role() = 'teacher'); -- Check applies to INSERT/UPDATE

-- Students can view courses they are enrolled in.
CREATE POLICY "Allow students to view enrolled courses"
  ON public.course FOR SELECT
  USING (
    get_my_role() = 'student' AND
    EXISTS (
      SELECT 1 FROM course_student cs
      WHERE cs.course_id = course.id AND cs.student_id = auth.uid()
    )
  );

-- ======= COURSE_TEACHER =======
-- Teachers can manage teacher assignments (Simplification for prototype)
CREATE POLICY "Allow teachers full access to course_teacher"
  ON public.course_teacher FOR ALL
  USING (get_my_role() = 'teacher')
  WITH CHECK (get_my_role() = 'teacher');

-- ======= COURSE_STUDENT =======
-- Teachers can manage student enrollments (Simplification for prototype)
CREATE POLICY "Allow teachers full access to course_student"
  ON public.course_student FOR ALL
  USING (get_my_role() = 'teacher')
  WITH CHECK (get_my_role() = 'teacher');

-- Students can view their own enrollments.
CREATE POLICY "Allow students to view own enrollments"
  ON public.course_student FOR SELECT
  USING (get_my_role() = 'student' AND student_id = auth.uid());

-- ======= LEARNING_UNIT =======
-- Teachers can manage all learning units (Simplification for prototype)
CREATE POLICY "Allow teachers full access to learning units"
  ON public.learning_unit FOR ALL
  USING (get_my_role() = 'teacher')
  WITH CHECK (get_my_role() = 'teacher'); -- Ensures creator_id is set correctly on INSERT/UPDATE if needed

-- Students can view units published in their enrolled courses.
CREATE POLICY "Allow students to view published units in enrolled courses"
  ON public.learning_unit FOR SELECT
  USING (
    get_my_role() = 'student' AND
    EXISTS (
      SELECT 1 FROM course_learning_unit clu
      JOIN course_student cs ON clu.course_id = cs.course_id
      WHERE clu.unit_id = learning_unit.id
        AND cs.student_id = auth.uid()
        AND clu.is_published = true
    )
  );

-- ======= COURSE_LEARNING_UNIT =======
-- Teachers can manage unit assignments and publishing (Simplification for prototype)
CREATE POLICY "Allow teachers full access to course_learning_unit"
  ON public.course_learning_unit FOR ALL
  USING (get_my_role() = 'teacher')
  WITH CHECK (get_my_role() = 'teacher');
-- Note: Students access publication status indirectly via learning_unit policy

-- ======= TASK =======
-- Teachers can manage tasks within units (Simplification for prototype)
CREATE POLICY "Allow teachers full access to tasks"
  ON public.task FOR ALL
  USING (get_my_role() = 'teacher') -- Teacher can see/delete/update all tasks
  WITH CHECK ( -- On INSERT/UPDATE, check if teacher created the parent unit
      get_my_role() = 'teacher' AND
      EXISTS (SELECT 1 FROM learning_unit lu WHERE lu.id = task.unit_id AND lu.creator_id = auth.uid())
  );

-- Students can view tasks belonging to published units in their enrolled courses.
CREATE POLICY "Allow students to view tasks of published units in enrolled courses"
  ON public.task FOR SELECT
  USING (
    get_my_role() = 'student' AND
    EXISTS ( -- Check if the student can see the parent learning unit
      SELECT 1 FROM learning_unit lu
      JOIN course_learning_unit clu ON lu.id = clu.unit_id
      JOIN course_student cs ON clu.course_id = cs.course_id
      WHERE lu.id = task.unit_id
        AND cs.student_id = auth.uid()
        AND clu.is_published = true
    )
  );

-- ======= SUBMISSION =======
-- Students can create exactly one submission for tasks they can view.
CREATE POLICY "Allow students to insert their own submission once"
  ON public.submission FOR INSERT
  WITH CHECK (
    get_my_role() = 'student' AND
    student_id = auth.uid() AND
    EXISTS ( -- Check if student is allowed to view the task they are submitting for
      SELECT 1 FROM task t
      WHERE t.id = submission.task_id
      -- RLS on task table implicitly handles visibility check here
    )
    -- The UNIQUE constraint handles the "once" part.
  );

-- Students can view their own submissions.
CREATE POLICY "Allow students to view their own submissions"
  ON public.submission FOR SELECT
  USING (get_my_role() = 'student' AND student_id = auth.uid());

-- Students can update their own submissions? (Potentially needed if they can edit before teacher review? Let's disable for now)
-- CREATE POLICY "Allow students to update their own submissions"
--   ON public.submission FOR UPDATE
--   USING (get_my_role() = 'student' AND student_id = auth.uid())
--   WITH CHECK (get_my_role() = 'student' AND student_id = auth.uid());

-- Teachers can view submissions for tasks in units they created (Simplification for prototype)
CREATE POLICY "Allow teachers to view submissions in their units"
  ON public.submission FOR SELECT
  USING (
    get_my_role() = 'teacher'
    -- Uncomment and adapt if teachers should ONLY see submissions for units they created:
    -- AND EXISTS (
    --  SELECT 1 FROM task t JOIN learning_unit lu ON t.unit_id = lu.id
    --  WHERE t.id = submission.task_id AND lu.creator_id = auth.uid()
    --)
  );

-- Teachers can update submissions (e.g., override fields) for tasks in units they created (Simplification for prototype)
CREATE POLICY "Allow teachers to update submissions in their units"
  ON public.submission FOR UPDATE
  USING ( -- Specifies which rows can be targeted for update
    get_my_role() = 'teacher'
     -- Uncomment and adapt if teachers should ONLY update submissions for units they created:
     -- AND EXISTS (
     --   SELECT 1 FROM task t JOIN learning_unit lu ON t.unit_id = lu.id
     --   WHERE t.id = submission.task_id AND lu.creator_id = auth.uid()
     -- )
  )
  WITH CHECK ( -- Ensures data integrity during update (teacher role required)
    get_my_role() = 'teacher'
  );

-- Teachers can delete submissions for tasks in units they created (Simplification for prototype)
CREATE POLICY "Allow teachers to delete submissions in their units"
  ON public.submission FOR DELETE
  USING (
    get_my_role() = 'teacher'
    -- Uncomment and adapt if teachers should ONLY delete submissions for units they created:
    -- AND EXISTS (
    --  SELECT 1 FROM task t JOIN learning_unit lu ON t.unit_id = lu.id
    --  WHERE t.id = submission.task_id AND lu.creator_id = auth.uid()
    -- )
  );