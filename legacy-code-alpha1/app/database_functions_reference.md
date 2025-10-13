# Database Functions Used in UI Pages

This is a complete reference of all database functions called from the UI pages in the Gustav application.

## Core Authentication & Session Functions
- `AuthSession.get_current_user()` - Get current authenticated user
- `get_user_supabase_client()` - Get authenticated Supabase client for current user

## Course Management Functions
- `get_courses_by_creator(teacher_id)` - Get courses created by a teacher
- `create_course(course_name, teacher_id)` - Create a new course
- `get_course_by_id(course_id)` - Get course details by ID
- `get_student_courses()` - Get courses assigned to student (from components)
- `get_user_course_ids(student_id)` - Get list of course IDs for a student

## Learning Unit Functions
- `get_learning_units_by_creator(teacher_id)` - Get units created by teacher
- `create_learning_unit(title, teacher_id)` - Create new learning unit
- `get_learning_unit_by_id(unit_id)` - Get unit details
- `get_assigned_units_for_course(course_id)` - Get units assigned to course

## Section Functions
- `get_sections_for_unit(unit_id)` - Get all sections for a unit
- `get_section_statuses_for_unit_in_course(unit_id, course_id)` - Get publish status of sections
- `publish_section_for_course(section_id, course_id)` - Publish section to course
- `unpublish_section_for_course(section_id, course_id)` - Unpublish section from course
- `get_published_section_details_for_student(unit_id, course_id, student_id)` - Get published sections with submission info

## Task Functions
- `get_task_details(task_id)` - Get detailed task information

## Submission Functions
- `create_submission(student_id, task_id, solution_text)` - Create new submission
- `get_submission_by_id(submission_id)` - Get submission details
- `get_submission_for_task(student_id, task_id)` - Get submission for specific task
- `get_submission_history(student_id, task_id)` - Get all submissions for task
- `update_submission_teacher_override(submission_id, teacher_feedback, teacher_grade)` - Teacher override feedback/grade
- `handle_file_submission(submission_result)` - Handle file uploads for submission
- `get_submission_status_matrix(course_id, unit_id)` - Get submission status for all students/tasks

## Feedback Functions
- `submit_feedback(type, subject, message)` - Submit platform feedback
- `get_all_feedback()` - Get all platform feedback (admin)
- `mark_feedback_as_viewed_safe(submission_id)` - Mark submission feedback as viewed

## Mastery/Wissensfestiger Functions
- `get_next_due_mastery_task()` - Get next due mastery task (deprecated)
- `get_next_mastery_task_or_unviewed_feedback(student_id, course_id)` - Get next mastery task or unviewed feedback
- `get_mastery_stats_for_student(student_id, course_id)` - Get mastery statistics

## Student/User Functions
- `get_students_in_course(course_id)` - Get all students enrolled in course
- `get_remaining_attempts(student_id, task_id)` - Get remaining attempts for task

## Utility Functions
- `MasterySessionState.get_course_state(course_id)` - Get mastery session state
- `MasterySessionState.is_task_active_in_other_course(task_id, course_id)` - Check if task active elsewhere
- `MasterySessionState.set_task(course_id, task)` - Set current task in session
- `MasterySessionState.mark_submitted(course_id, task_id, submission_id)` - Mark task as submitted
- `MasterySessionState.clear_task(course_id, keep_feedback_context)` - Clear current task

## Cookie/Session Test Functions (Debug Pages)
- `get_cookie_controller()` - Get cookie controller instance
- `get_cookie_manager()` - Get cookie manager instance
- `get_fernet()` - Get encryption instance

## Page-to-Function Mapping

### 0_Startseite.py
- No database functions used

### 1_Kurse.py
- `get_course_by_id()`
- `get_courses_by_creator()`
- `create_course()`

### 2_Lerneinheiten.py
- `get_learning_units_by_creator()`
- `create_learning_unit()`
- `get_learning_unit_by_id()`
- `get_assigned_units_for_course()`

### 3_Meine_Aufgaben.py
- `get_published_section_details_for_student()`
- `create_submission()`
- `get_submission_by_id()`
- `get_submission_history()`
- `get_remaining_attempts()`
- `handle_file_submission()`
- `get_user_supabase_client()`

### 5_Schueler.py
- `get_students_in_course()`

### 6_Live-Unterricht.py
- `get_sections_for_unit()`
- `get_section_statuses_for_unit_in_course()`
- `publish_section_for_course()`
- `unpublish_section_for_course()`
- `get_submission_status_matrix()`
- `get_task_details()`
- `get_submission_for_task()`
- `update_submission_teacher_override()`

### 7_Wissensfestiger.py
- `get_next_due_mastery_task()`
- `get_next_mastery_task_or_unviewed_feedback()`
- `create_submission()`
- `get_mastery_stats_for_student()`
- `get_user_course_ids()`
- `get_submission_by_id()`
- `mark_feedback_as_viewed_safe()`
- `get_user_supabase_client()`
- `MasterySessionState.*` functions

### 8_Feedback_geben.py
- `submit_feedback()`
- `get_user_supabase_client()`

### 9_Feedback_einsehen.py
- `get_all_feedback()`
- `get_user_supabase_client()`

### 99_Debug_Headers.py
- `AuthSession.get_current_user()`

### 98_Cookie_Test_ESC.py & 99_Cookie_Test.py
- Cookie management functions (test/debug only)

## Notes
1. Most functions are imported from `utils.db_queries`
2. Some functions come from specialized modules like `utils.db.platform.feedback`
3. Authentication uses `AuthSession` from `utils.auth_session`
4. File handling uses storage operations via `get_user_supabase_client()`
5. Components may import additional database functions not listed here