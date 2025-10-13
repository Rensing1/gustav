-- Phase 2: Task Type Separation - New Table Structure
-- Creates the Domain-Driven Design structure with task_base, regular_tasks, mastery_tasks

-- Base table for shared task attributes (all columns from current task table)
CREATE TABLE task_base (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id uuid REFERENCES unit_section(id),
    instruction text NOT NULL,
    task_type text,                    -- Legacy support from old task table
    criteria text,                     -- Legacy support from old task table  
    assessment_criteria jsonb,
    solution_hints text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- Regular tasks table (inherits from task_base)
CREATE TABLE regular_tasks (
    task_id uuid PRIMARY KEY REFERENCES task_base(id) ON DELETE CASCADE,
    order_in_section integer NOT NULL DEFAULT 1,
    max_attempts integer DEFAULT 1
);

-- Mastery tasks table (inherits from task_base)  
CREATE TABLE mastery_tasks (
    task_id uuid PRIMARY KEY REFERENCES task_base(id) ON DELETE CASCADE
    -- No max_attempts - controlled by spaced repetition algorithm
    -- No order_in_section - presented based on due dates
);

-- RLS Policies - Copy from existing task table
-- Enable RLS on new tables
ALTER TABLE task_base ENABLE ROW LEVEL SECURITY;
ALTER TABLE regular_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE mastery_tasks ENABLE ROW LEVEL SECURITY;

-- Policy for task_base: Students can view tasks in published sections
CREATE POLICY "Students view tasks in published sections" ON task_base
    FOR SELECT USING (
        get_my_role() = 'student' AND
        EXISTS (
            SELECT 1 FROM unit_section us
            WHERE us.id = task_base.section_id
        )
    );

-- Policy for task_base: Teachers can manage tasks in their units  
CREATE POLICY "Teachers manage tasks in their units" ON task_base
    FOR ALL USING (
        get_my_role() = 'teacher' AND
        EXISTS (
            SELECT 1 FROM unit_section us
            JOIN learning_unit lu ON us.unit_id = lu.id
            WHERE us.id = task_base.section_id 
            AND lu.creator_id = auth.uid()
        )
    )
    WITH CHECK (
        get_my_role() = 'teacher' AND
        EXISTS (
            SELECT 1 FROM unit_section us
            JOIN learning_unit lu ON us.unit_id = lu.id
            WHERE us.id = task_base.section_id 
            AND lu.creator_id = auth.uid()
        )
    );

-- Policies for regular_tasks: Inherit from task_base via FK
CREATE POLICY "Access regular tasks via task_base" ON regular_tasks
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM task_base tb 
            WHERE tb.id = regular_tasks.task_id
        )
    );

-- Policies for mastery_tasks: Inherit from task_base via FK  
CREATE POLICY "Access mastery tasks via task_base" ON mastery_tasks
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM task_base tb 
            WHERE tb.id = mastery_tasks.task_id
        )
    );

-- Comments for documentation
COMMENT ON TABLE task_base IS 'Base table for all tasks - Phase 2 of Task Type Separation. Contains shared attributes.';
COMMENT ON TABLE regular_tasks IS 'Regular tasks with order and attempt limits - Phase 2 of Task Type Separation.';
COMMENT ON TABLE mastery_tasks IS 'Mastery tasks (Wissensfestiger) for spaced repetition - Phase 2 of Task Type Separation.';