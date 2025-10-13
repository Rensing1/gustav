-- Migration: Add trigger to ensure feedback status is properly set
-- Purpose: Fix issues with feedback status not being updated correctly

-- Add index for faster feedback status queries
CREATE INDEX IF NOT EXISTS idx_submission_feedback_status 
ON submission(feedback_status, created_at DESC)
WHERE feedback_status IN ('pending', 'processing', 'retry');

-- Create function to ensure feedback fields are consistent
CREATE OR REPLACE FUNCTION ensure_feedback_consistency()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- If ai_feedback is set, ensure status is completed
    IF NEW.ai_feedback IS NOT NULL AND NEW.feedback_status IN ('pending', 'processing') THEN
        NEW.feedback_status = 'completed';
    END IF;
    
    -- If feed_back_text and feed_forward_text are set, ensure status is completed
    IF NEW.feed_back_text IS NOT NULL AND NEW.feed_forward_text IS NOT NULL AND NEW.feedback_status IN ('pending', 'processing') THEN
        NEW.feedback_status = 'completed';
    END IF;
    
    RETURN NEW;
END;
$$;

-- Create trigger to ensure consistency
DROP TRIGGER IF EXISTS ensure_feedback_consistency_trigger ON submission;
CREATE TRIGGER ensure_feedback_consistency_trigger
    BEFORE INSERT OR UPDATE ON submission
    FOR EACH ROW
    EXECUTE FUNCTION ensure_feedback_consistency();

-- Fix any existing inconsistencies
UPDATE submission
SET feedback_status = 'completed'
WHERE (ai_feedback IS NOT NULL OR (feed_back_text IS NOT NULL AND feed_forward_text IS NOT NULL))
AND feedback_status IN ('pending', 'processing', 'retry');

-- Add comment
COMMENT ON FUNCTION ensure_feedback_consistency() IS 'Ensures feedback_status is consistent with actual feedback data';