-- Drop the Helena-related table. Indexes associated with it are dropped automatically.
DROP TABLE public.student_mastery_progress;

-- Rename the archived SM-2 table back to the active name.
ALTER TABLE public.student_mastery_progress_sm2_archive RENAME TO student_mastery_progress;
