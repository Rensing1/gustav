-- Clean up duplicate create_regular_task and create_mastery_task functions

-- Drop old versions of create_regular_task
DROP FUNCTION IF EXISTS public.create_regular_task(text,uuid,text,text,integer,integer,text[]);
DROP FUNCTION IF EXISTS public.create_regular_task(text,uuid,text,text,text,integer,integer,text[]);

-- Drop old versions of create_mastery_task if they exist
DROP FUNCTION IF EXISTS public.create_mastery_task(text,uuid,text,text,integer,text);
DROP FUNCTION IF EXISTS public.create_mastery_task(text,uuid,text,text,text,integer,text);