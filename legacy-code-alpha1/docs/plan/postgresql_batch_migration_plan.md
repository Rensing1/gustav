# PostgreSQL Batch Migration Plan

## Schema-Verifizierung

### Kritische Schema-Probleme (Vorab zu klären):

1. **Views benötigt:**
   - `all_regular_tasks` - Vereint `task_base` + `regular_tasks`
   - `all_mastery_tasks` - Vereint `task_base` + `mastery_tasks`

2. **Tabellen-Struktur:**
   - `task_base` (id, section_id, title, task_type, order_in_section, created_at)
   - `regular_tasks` (task_id, prompt, max_attempts, grading_criteria)
   - `mastery_tasks` (task_id, prompt, difficulty_level, concept_explanation)

3. **Bekannte Schema-Fixes:**
   - ✅ `unit_assignment` → `course_learning_unit_assignment`
   - ✅ `section` → `unit_section`
   - ✅ `learning_unit.description` existiert nicht

## Batch-Aufteilung (10 Functions pro Migration)

### Batch 1: Simple READ Operations
1. `get_users_by_role` - profiles
2. `get_students_in_course` - course_student + profiles
3. `get_teachers_in_course` - course_teacher + profiles
4. `get_courses_assigned_to_unit` - course_learning_unit_assignment + course
5. `get_user_course_ids` - course_student
6. `get_student_courses` - course_student + course
7. `get_course_by_id` - course
8. `get_submission_by_id` - submission
9. `get_submission_history` - submission
10. `get_all_feedback` - feedback

**Schema-Risiken:** Minimal, alle Tabellen existieren

### Batch 2: User/Course Management
1. `add_user_to_course` - course_student/course_teacher (dynamic)
2. `remove_user_from_course` - course_student/course_teacher (dynamic)
3. `assign_unit_to_course` - course_learning_unit_assignment
4. `unassign_unit_from_course` - course_learning_unit_assignment
5. `update_course` - course
6. `delete_course` - course
7. `is_teacher_authorized_for_course` - course_teacher
8. `get_course_students` - course_student + profiles
9. `update_learning_unit` - learning_unit
10. `delete_learning_unit` - learning_unit

**Schema-Risiken:** Dynamic table selection bei add/remove_user

### Batch 3: Task CRUD Operations
1. `create_regular_task` - task_base + regular_tasks
2. `create_mastery_task` - task_base + mastery_tasks
3. `create_task_in_new_structure` - Router function
4. `update_task_in_new_structure` - task_base + regular_tasks/mastery_tasks
5. `delete_task_in_new_structure` - task_base
6. `get_tasks_for_section` - all_regular_tasks/all_mastery_tasks
7. `get_regular_tasks_for_section` - all_regular_tasks
8. `get_mastery_tasks_for_section` - all_mastery_tasks
9. `move_task_up` - all_regular_tasks
10. `move_task_down` - all_regular_tasks

**Schema-Risiken:** Views müssen existieren, Transaktionen bei create/update

### Batch 4: Submission System
1. `create_submission` - submission + all_regular_tasks/all_mastery_tasks
2. `get_submission_for_task` - submission
3. `get_remaining_attempts` - all_regular_tasks + submission
4. `get_task_details` - all_regular_tasks/all_mastery_tasks
5. `update_submission_ai_results` - submission
6. `update_submission_teacher_override` - submission
7. `mark_feedback_as_viewed_safe` - submission
8. `save_mastery_submission` - mastery_submission
9. `submit_feedback` - feedback
10. `calculate_learning_streak` - submission

**Schema-Risiken:** Task type detection, Views benötigt

### Batch 5: Complex Queries & Matrix
1. `get_published_section_details_for_student` - SEHR KOMPLEX
2. `get_submissions_for_course_and_unit` - KOMPLEX
3. `_get_submission_status_matrix_uncached` - SEHR KOMPLEX
4. `get_submission_status_matrix` - Wrapper
5. `get_section_statuses_for_unit_in_course` - unit_section + course_unit_section_status
6. `publish_section_for_course` - course_unit_section_status
7. `unpublish_section_for_course` - course_unit_section_status
8. `create_section` - unit_section
9. `update_section_materials` - unit_section
10. `get_section_tasks` - all_regular_tasks/all_mastery_tasks

**Schema-Risiken:** Performance-kritisch, evtl. Materialized Views nötig

### Batch 6: Mastery & Feedback System
1. `get_mastery_tasks_for_course` - Multi-Join
2. `get_next_due_mastery_task` - student_mastery_progress + all_mastery_tasks
3. `get_next_mastery_task_or_unviewed_feedback` - Wrapper
4. `submit_mastery_answer` - submission + student_mastery_progress
5. `get_mastery_stats_for_student` - RPC call
6. `get_mastery_overview_for_teacher` - course_student + student_mastery_progress

**Schema-Risiken:** Spaced repetition logic, RPC dependencies

## Status Update (2025-09-08)

### ✅ Batch 1: COMPLETED
- **SQL Migration:** `20250908162120_batch1_simple_read_operations.sql` deployed
- **Python Updates:** 2/10 functions updated
  - ✅ `get_users_by_role()`
  - ✅ `get_students_in_course()`
  - ⏳ Remaining 8 functions pending

### 🔄 Current Tasks
- Complete Python wrapper updates for Batch 1
- Test all 10 functions
- Deploy container restart

## Nächste Schritte

1. **Views erstellen** (falls nicht vorhanden):
   ```sql
   CREATE OR REPLACE VIEW all_regular_tasks AS
   SELECT 
     t.id,
     t.section_id,
     t.title,
     t.task_type,
     t.order_in_section,
     t.created_at,
     r.prompt,
     r.max_attempts,
     r.grading_criteria,
     FALSE as is_mastery
   FROM task_base t
   JOIN regular_tasks r ON r.task_id = t.id;
   
   CREATE OR REPLACE VIEW all_mastery_tasks AS
   SELECT
     t.id,
     t.section_id,
     t.title,
     t.task_type,
     t.order_in_section,
     t.created_at,
     m.prompt,
     m.difficulty_level,
     m.concept_explanation,
     TRUE as is_mastery
   FROM task_base t
   JOIN mastery_tasks m ON m.task_id = t.id;
   ```

2. **Batch 1 fertigstellen** (8 verbleibende Python Updates)
3. **Batch 2 Migration vorbereiten** (User/Course Management)