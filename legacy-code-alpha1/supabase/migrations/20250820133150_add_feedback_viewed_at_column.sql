-- Add feedback_viewed_at column to submission table
-- This tracks when a student has seen the feedback for their submission

ALTER TABLE submission 
ADD COLUMN feedback_viewed_at TIMESTAMP WITH TIME ZONE;

-- Add comment for documentation
COMMENT ON COLUMN submission.feedback_viewed_at IS 'Timestamp when the student viewed the feedback (clicked Next Task button)';