-- Phase 1: Archive the old SM-2 table to preserve all existing data.
ALTER TABLE public.student_mastery_progress RENAME TO student_mastery_progress_sm2_archive;

-- Phase 2: Create the new table for the Helena algorithm.
CREATE TABLE public.student_mastery_progress (
    student_id UUID NOT NULL,
    task_id UUID NOT NULL,
    stability FLOAT DEFAULT 0.5,
    difficulty FLOAT DEFAULT 5.0,
    last_attempt_date DATE,
    last_score INT CHECK (last_score >= 1 AND last_score <= 5),
    total_attempts INT DEFAULT 0,
    next_due_date DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (student_id, task_id),
    FOREIGN KEY (student_id) REFERENCES public.profiles(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES public.task(id) ON DELETE CASCADE
);

-- Add comments for documentation
COMMENT ON TABLE public.student_mastery_progress IS 'Tracks spaced repetition progress using the Helena algorithm.';
COMMENT ON COLUMN public.student_mastery_progress.stability IS 'S: How deep a memory is rooted (in days).';
COMMENT ON COLUMN public.student_mastery_progress.difficulty IS 'D: The intrinsic difficulty of the task (1-10).';
COMMENT ON COLUMN public.student_mastery_progress.next_due_date IS 'The date the task is scheduled for review.';

-- Create indexes for performance
CREATE INDEX idx_helena_mastery_progress_due ON public.student_mastery_progress(student_id, next_due_date);
CREATE INDEX idx_helena_mastery_progress_task ON public.student_mastery_progress(task_id);

-- Re-apply the updated_at trigger to the new table
-- The function update_updated_at_column() already exists from a previous migration.
CREATE TRIGGER update_student_mastery_progress_updated_at
    BEFORE UPDATE ON public.student_mastery_progress
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- Re-create Row Level Security policies for the new table
ALTER TABLE public.student_mastery_progress ENABLE ROW LEVEL SECURITY;

-- Students can only see their own progress
CREATE POLICY "Students can view own mastery progress" ON public.student_mastery_progress
    FOR SELECT USING (auth.uid() = student_id);

-- Students can insert their own progress records
CREATE POLICY "Students can create own mastery progress" ON public.student_mastery_progress
    FOR INSERT WITH CHECK (auth.uid() = student_id);

-- Students can update their own progress records
CREATE POLICY "Students can update own mastery progress" ON public.student_mastery_progress
    FOR UPDATE USING (auth.uid() = student_id);

-- Teachers can view progress for students in their courses
CREATE POLICY "Teachers can view student mastery progress" ON public.student_mastery_progress
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.profiles p
            WHERE p.id = auth.uid()
            AND p.role = 'teacher'
        )
        AND EXISTS (
            SELECT 1 FROM public.task t
            JOIN public.unit_section us ON t.section_id = us.id
            JOIN public.learning_unit lu ON us.unit_id = lu.id
            WHERE t.id = student_mastery_progress.task_id
            AND lu.creator_id = auth.uid()
        )
    );
