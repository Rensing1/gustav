-- Simplify tasks by removing the title column

-- First, alter the column to drop the NOT NULL constraint.
-- This is a good practice in case there are any dependencies or complex constraints.
ALTER TABLE public.task ALTER COLUMN title DROP NOT NULL;

-- Now, drop the column entirely.
ALTER TABLE public.task DROP COLUMN title;
