-- Clean up duplicate create_mastery_task functions

-- Drop old versions
DROP FUNCTION IF EXISTS public.create_mastery_task(text,uuid,text,text,integer,integer,text[]);
DROP FUNCTION IF EXISTS public.create_mastery_task(text,uuid,text,text,text,jsonb,text,integer);