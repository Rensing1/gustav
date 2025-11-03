-- Learning submissions: strengthen idempotency uniqueness for ON CONFLICT
-- Why:
--   Our repository uses `INSERT ... ON CONFLICT (course_id, task_id, student_sub, idempotency_key)`
--   to implement HTTP Idempotency-Key semantics. The previous implementation
--   relied on a partial unique index, which complicates inference in ON CONFLICT.
--   We switch to a proper UNIQUE constraint across these columns so that
--   conflict detection is reliable while still allowing multiple NULL keys
--   (Postgres treats NULLs as distinct for UNIQUE constraints).

begin;

-- Drop the old partial unique index if present.
drop index if exists public.idx_learning_submissions_idempotency_key;

-- Add a real UNIQUE constraint. This permits many NULL idempotency_key rows
-- (desired: no idempotency when key missing) and guarantees uniqueness for
-- non-NULL keys per (course, task, student).
alter table public.learning_submissions
    add constraint learning_submissions_idempotency_unique
    unique (course_id, task_id, student_sub, idempotency_key);

commit;

