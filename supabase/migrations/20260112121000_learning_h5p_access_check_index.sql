-- Learning: H5P access-check performance index.
--
-- Why:
--   `DBLearningRepo.is_h5p_content_released_for_student(...)` filters by
--   `unit_tasks.kind='h5p'` and `unit_tasks.h5p_content_id = <content_id>`.
--   A partial index keeps this check fast as the number of tasks grows.

create index if not exists idx_unit_tasks_h5p_content_id
  on public.unit_tasks (h5p_content_id)
  where kind = 'h5p' and h5p_content_id is not null;

