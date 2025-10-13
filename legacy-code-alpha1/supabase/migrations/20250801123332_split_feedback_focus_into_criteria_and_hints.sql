-- Migration: Split feedback_focus into assessment_criteria and solution_hints
-- Description: Replaces the single feedback_focus text field with structured criteria and hints
-- Date: 2025-08-01

-- First, delete all existing tasks and their related data (test data only)
DELETE FROM submission;
DELETE FROM task;

-- Drop the old feedback_focus column and add new columns
ALTER TABLE task 
DROP COLUMN IF EXISTS feedback_focus,
ADD COLUMN assessment_criteria JSONB DEFAULT '[]'::jsonb CHECK (
    jsonb_typeof(assessment_criteria) = 'array' AND
    jsonb_array_length(assessment_criteria) <= 5
),
ADD COLUMN solution_hints TEXT;

-- Add comments for documentation
COMMENT ON COLUMN task.assessment_criteria IS 'Array of assessment criteria (max 5) that will be used for AI feedback generation';
COMMENT ON COLUMN task.solution_hints IS 'Teacher-provided solution hints or model solution to guide the AI analysis';

-- Update the submission table to support structured feedback
ALTER TABLE submission
ADD COLUMN IF NOT EXISTS feed_back_text TEXT,
ADD COLUMN IF NOT EXISTS feed_forward_text TEXT;

-- Add comments for new feedback columns
COMMENT ON COLUMN submission.feed_back_text IS 'The descriptive part of the feedback (Where am I?)';
COMMENT ON COLUMN submission.feed_forward_text IS 'The actionable part of the feedback (Where to go next?)';