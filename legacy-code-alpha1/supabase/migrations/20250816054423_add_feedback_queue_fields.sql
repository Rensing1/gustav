-- Migration: Add feedback queue fields to submission table
-- Purpose: Enable asynchronous AI feedback processing with retry mechanism

-- Add new columns for feedback queue management
ALTER TABLE submission 
ADD COLUMN IF NOT EXISTS feedback_status TEXT DEFAULT 'pending' 
    CHECK (feedback_status IN ('pending', 'processing', 'completed', 'failed', 'retry')),
ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0 
    CHECK (retry_count >= 0 AND retry_count <= 3),
ADD COLUMN IF NOT EXISTS last_retry_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS processing_started_at TIMESTAMP WITH TIME ZONE;

-- Create index for efficient queue queries
CREATE INDEX IF NOT EXISTS idx_submission_feedback_queue 
ON submission(feedback_status, retry_count, created_at) 
WHERE feedback_status IN ('pending', 'retry');

-- Create index for finding stuck jobs
CREATE INDEX IF NOT EXISTS idx_submission_processing_timeout
ON submission(processing_started_at)
WHERE feedback_status = 'processing';

-- Add comment to document the purpose
COMMENT ON COLUMN submission.feedback_status IS 'Status of AI feedback generation: pending (waiting), processing (in progress), completed (done), failed (permanent failure), retry (temporary failure, will retry)';
COMMENT ON COLUMN submission.retry_count IS 'Number of times feedback generation has been retried (max 3)';
COMMENT ON COLUMN submission.last_retry_at IS 'Timestamp of last retry attempt, used for exponential backoff';
COMMENT ON COLUMN submission.processing_started_at IS 'When processing started, used to detect stuck jobs';

-- Create function to get next submission from queue (with row locking)
CREATE OR REPLACE FUNCTION get_next_feedback_submission()
RETURNS TABLE (
    id UUID,
    task_id UUID,
    student_id UUID,
    submission_data JSONB,
    retry_count INTEGER
) 
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    WITH next_submission AS (
        SELECT s.id
        FROM submission s
        WHERE s.feedback_status IN ('pending', 'retry')
        AND s.retry_count < 3
        AND (
            s.last_retry_at IS NULL 
            OR s.last_retry_at < NOW() - (s.retry_count * INTERVAL '5 minutes')
        )
        ORDER BY 
            CASE WHEN s.feedback_status = 'pending' THEN 0 ELSE 1 END, -- pending first
            s.created_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED -- Prevent race conditions
    )
    UPDATE submission s
    SET 
        feedback_status = 'processing',
        processing_started_at = NOW()
    FROM next_submission ns
    WHERE s.id = ns.id
    RETURNING 
        s.id,
        s.task_id,
        s.student_id,
        s.submission_data,
        s.retry_count;
END;
$$;

-- Create function to mark submission as completed
CREATE OR REPLACE FUNCTION mark_feedback_completed(
    p_submission_id UUID,
    p_feedback TEXT,
    p_insights JSONB DEFAULT NULL,
    p_mastery_scores JSONB DEFAULT NULL
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE submission
    SET 
        feedback_status = 'completed',
        ai_feedback = p_feedback,
        ai_insights = p_insights,
        ai_mastery_scores = p_mastery_scores
    WHERE id = p_submission_id
    AND feedback_status = 'processing';
    
    RETURN FOUND;
END;
$$;

-- Create function to handle feedback generation failure
CREATE OR REPLACE FUNCTION mark_feedback_failed(
    p_submission_id UUID,
    p_error_message TEXT DEFAULT NULL
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_retry_count INTEGER;
BEGIN
    -- Get current retry count
    SELECT retry_count INTO v_retry_count
    FROM submission
    WHERE id = p_submission_id
    AND feedback_status = 'processing';
    
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;
    
    -- Update based on retry count
    IF v_retry_count < 3 THEN
        UPDATE submission
        SET 
            feedback_status = 'retry',
            retry_count = retry_count + 1,
            last_retry_at = NOW(),
            processing_started_at = NULL
        WHERE id = p_submission_id;
    ELSE
        UPDATE submission
        SET 
            feedback_status = 'failed',
            ai_feedback = COALESCE(p_error_message, 'Feedback-Generierung fehlgeschlagen nach 3 Versuchen'),
            processing_started_at = NULL
        WHERE id = p_submission_id;
    END IF;
    
    RETURN TRUE;
END;
$$;

-- Create function to reset stuck jobs (processing > 5 minutes)
CREATE OR REPLACE FUNCTION reset_stuck_feedback_jobs()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    rows_updated INTEGER;
BEGIN
    UPDATE submission
    SET 
        feedback_status = 'retry',
        retry_count = retry_count + 1,
        last_retry_at = NOW(),
        processing_started_at = NULL
    WHERE feedback_status = 'processing'
    AND processing_started_at < NOW() - INTERVAL '5 minutes'
    AND retry_count < 3;
    
    GET DIAGNOSTICS rows_updated = ROW_COUNT;
    
    -- Mark as failed if already retried 3 times
    UPDATE submission
    SET 
        feedback_status = 'failed',
        ai_feedback = 'Feedback-Generierung timeout nach 3 Versuchen',
        processing_started_at = NULL
    WHERE feedback_status = 'processing'
    AND processing_started_at < NOW() - INTERVAL '5 minutes'
    AND retry_count >= 3;
    
    RETURN rows_updated;
END;
$$;

-- Create function to get queue position for a submission
CREATE OR REPLACE FUNCTION get_submission_queue_position(p_submission_id UUID)
RETURNS INTEGER
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_position INTEGER;
    v_created_at TIMESTAMP;
    v_status TEXT;
BEGIN
    -- Get submission details
    SELECT created_at, feedback_status INTO v_created_at, v_status
    FROM submission
    WHERE id = p_submission_id;
    
    IF NOT FOUND OR v_status NOT IN ('pending', 'retry', 'processing') THEN
        RETURN NULL;
    END IF;
    
    -- Count submissions ahead in queue
    SELECT COUNT(*) + 1 INTO v_position
    FROM submission
    WHERE feedback_status IN ('pending', 'retry', 'processing')
    AND created_at < v_created_at
    AND retry_count < 3;
    
    RETURN v_position;
END;
$$;

-- Grant execute permissions on new functions
GRANT EXECUTE ON FUNCTION get_next_feedback_submission() TO service_role;
GRANT EXECUTE ON FUNCTION mark_feedback_completed(UUID, TEXT, JSONB, JSONB) TO service_role;
GRANT EXECUTE ON FUNCTION mark_feedback_failed(UUID, TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION reset_stuck_feedback_jobs() TO service_role;
GRANT EXECUTE ON FUNCTION get_submission_queue_position(UUID) TO authenticated;

-- Add RLS policy for feedback_status visibility
CREATE POLICY "Students can see their own submission feedback status" 
ON submission 
FOR SELECT 
USING (auth.uid() = student_id);