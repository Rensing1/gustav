alter table if exists public.learning_submissions
  add column if not exists intent text not null default 'submit';

alter table if exists public.learning_submissions
  drop constraint if exists learning_submissions_intent_check;

alter table public.learning_submissions
  add constraint learning_submissions_intent_check
  check (intent in ('feedback', 'submit'));
