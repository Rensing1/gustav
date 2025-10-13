-- Create table for tracking student mastery progress
CREATE TABLE student_mastery_progress (
    student_id UUID NOT NULL,
    task_id UUID NOT NULL,
    current_interval INT DEFAULT 1,
    next_due_date DATE DEFAULT CURRENT_DATE,
    ease_factor FLOAT DEFAULT 2.5,
    repetition_count INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'learning' CHECK (status IN ('learning', 'reviewing', 'relearning')),
    learning_step_index INT DEFAULT 0,
    relearning_step_index INT DEFAULT 0,
    last_attempt_date DATE,
    last_score INT CHECK (last_score >= 1 AND last_score <= 5),
    total_attempts INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (student_id, task_id),
    FOREIGN KEY (student_id) REFERENCES profiles(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES task(id) ON DELETE CASCADE
);

-- Add comments for documentation
COMMENT ON TABLE student_mastery_progress IS 'Tracks spaced repetition progress for mastery tasks per student';
COMMENT ON COLUMN student_mastery_progress.status IS 'Current learning status: learning (new), reviewing (graduated), relearning (lapsed)';
COMMENT ON COLUMN student_mastery_progress.ease_factor IS 'SM-2 algorithm ease factor, affects interval growth';
COMMENT ON COLUMN student_mastery_progress.last_score IS 'Last AI assessment score (1-5)';

-- Create indexes for performance
CREATE INDEX idx_mastery_progress_due ON student_mastery_progress(student_id, next_due_date);
CREATE INDEX idx_mastery_progress_task ON student_mastery_progress(task_id);
CREATE INDEX idx_mastery_progress_status ON student_mastery_progress(student_id, status);

-- Create updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_student_mastery_progress_updated_at
    BEFORE UPDATE ON student_mastery_progress
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Row Level Security
ALTER TABLE student_mastery_progress ENABLE ROW LEVEL SECURITY;

-- Students can only see their own progress
CREATE POLICY "Students can view own mastery progress" ON student_mastery_progress
    FOR SELECT USING (auth.uid() = student_id);

-- Students can insert their own progress records
CREATE POLICY "Students can create own mastery progress" ON student_mastery_progress
    FOR INSERT WITH CHECK (auth.uid() = student_id);

-- Students can update their own progress records
CREATE POLICY "Students can update own mastery progress" ON student_mastery_progress
    FOR UPDATE USING (auth.uid() = student_id);

-- Teachers can view progress for students in their courses
CREATE POLICY "Teachers can view student mastery progress" ON student_mastery_progress
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = auth.uid() 
            AND p.role = 'teacher'
        )
        AND EXISTS (
            SELECT 1 FROM task t
            JOIN unit_section us ON t.section_id = us.id
            JOIN learning_unit lu ON us.unit_id = lu.id
            WHERE t.id = student_mastery_progress.task_id
            AND lu.creator_id = auth.uid()
        )
    );