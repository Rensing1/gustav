-- Fix feedback_type constraint to include 'bug' option
-- This aligns with the submit_feedback function that already allows 'bug' type

-- Drop the existing constraint
ALTER TABLE feedback DROP CONSTRAINT IF EXISTS feedback_feedback_type_check;

-- Add new constraint that includes 'bug'
ALTER TABLE feedback ADD CONSTRAINT feedback_feedback_type_check 
    CHECK (feedback_type IN ('unterricht', 'plattform', 'bug'));

-- Add comment explaining the change
COMMENT ON COLUMN feedback.feedback_type IS 'Type of feedback: unterricht (teaching), plattform (platform), or bug (bug report)';