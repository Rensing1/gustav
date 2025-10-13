-- Create feedback table for anonymous student feedback
CREATE TABLE IF NOT EXISTS feedback (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    feedback_type TEXT NOT NULL CHECK (feedback_type IN ('unterricht', 'plattform')),
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Add RLS policies
ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;

-- Students can insert feedback (anonymous - no user check)
CREATE POLICY "Students can submit feedback" ON feedback
    FOR INSERT 
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM profiles 
            WHERE profiles.id = auth.uid() 
            AND profiles.role = 'student'
        )
    );

-- Teachers can view all feedback
CREATE POLICY "Teachers can view feedback" ON feedback
    FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM profiles 
            WHERE profiles.id = auth.uid() 
            AND profiles.role = 'teacher'
        )
    );

-- Create index for performance
CREATE INDEX idx_feedback_created_at ON feedback(created_at DESC);
CREATE INDEX idx_feedback_type ON feedback(feedback_type);

-- Disable RLS for feedback table to simplify access
ALTER TABLE feedback DISABLE ROW LEVEL SECURITY;
