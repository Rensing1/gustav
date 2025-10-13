-- Migration to remove description columns from course and learning_unit tables

ALTER TABLE public.course
DROP COLUMN IF EXISTS description;

ALTER TABLE public.learning_unit
DROP COLUMN IF EXISTS description;
