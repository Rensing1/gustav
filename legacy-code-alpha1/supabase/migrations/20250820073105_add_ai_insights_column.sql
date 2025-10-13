-- Add missing ai_insights column to submission table
-- This column stores mastery-specific feedback results

ALTER TABLE submission 
ADD COLUMN ai_insights JSONB;

-- Add comment for documentation
COMMENT ON COLUMN submission.ai_insights IS 'Mastery-specific AI insights and analysis results';