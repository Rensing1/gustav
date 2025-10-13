# PostgreSQL Migration Analysis - db_queries.py

## Overview
Analysis of all functions in db_queries.py that need migration to PostgreSQL functions.

## Already Migrated Functions (Skip These)
- get_courses_by_creator
- get_learning_units_by_creator
- get_learning_unit_by_id
- create_learning_unit
- create_course
- get_assigned_units_for_course
- get_sections_for_unit

## Functions to Migrate

### 1. create_regular_task
**Type:** WRITE (Complex)
**Tables Accessed:**
- task_base (INSERT)
- regular_tasks (INSERT)
**Schema Issues:**
- Uses new task structure with base/specific tables
- Needs transaction with rollback capability
**Special Considerations:**
- Two-step insert process with rollback on failure
- Returns combined data from both tables

### 2. create_mastery_task
**Type:** WRITE (Complex)
**Tables Accessed:**
- task_base (INSERT)
- mastery_tasks (INSERT)
**Schema Issues:**
- Similar to create_regular_task but for mastery tasks
- Needs transaction with rollback capability
**Special Considerations:**
- Two-step insert process with rollback on failure

### 3. create_task_in_new_structure
**Type:** WRITE (Router)
**Tables Accessed:**
- Calls either create_regular_task or create_mastery_task
**Special Considerations:**
- Routes based on is_mastery flag
- Could be simplified in PostgreSQL

### 4. update_task_in_new_structure
**Type:** WRITE (Complex)
**Tables Accessed:**
- task_base (SELECT, UPDATE)
- regular_tasks (UPDATE)
- mastery_tasks (JOIN in SELECT)
**Schema Issues:**
- Complex join to determine task type
- Conditional updates based on task type
**Special Considerations:**
- Needs to handle both base and specific table updates

### 5. delete_task_in_new_structure
**Type:** WRITE
**Tables Accessed:**
- task_base (DELETE)
**Special Considerations:**
- Relies on CASCADE for cleanup
- Simple implementation

### 6. get_users_by_role
**Type:** READ
**Tables Accessed:**
- profiles (SELECT)
**Schema Issues:**
- Table name correct, should work as-is
**Special Considerations:**
- Simple query with role filter

### 7. get_students_in_course
**Type:** READ
**Tables Accessed:**
- course_student (SELECT)
- profiles (JOIN)
**Schema Issues:**
- Uses proper join syntax
**Special Considerations:**
- Returns nested profile data

### 8. get_teachers_in_course
**Type:** READ
**Tables Accessed:**
- course_teacher (SELECT)
- profiles (JOIN)
**Schema Issues:**
- Similar to get_students_in_course
**Special Considerations:**
- Returns nested profile data

### 9. add_user_to_course
**Type:** WRITE
**Tables Accessed:**
- course_student OR course_teacher (INSERT)
**Special Considerations:**
- Dynamic table selection based on role
- Should check for existing assignment

### 10. remove_user_from_course
**Type:** WRITE
**Tables Accessed:**
- course_student OR course_teacher (DELETE)
**Special Considerations:**
- Dynamic table selection based on role

### 11. get_courses_assigned_to_unit
**Type:** READ
**Tables Accessed:**
- course_learning_unit_assignment (SELECT)
- course (JOIN)
**Special Considerations:**
- Returns course details for a unit

### 12. assign_unit_to_course
**Type:** WRITE
**Tables Accessed:**
- course_learning_unit_assignment (INSERT)
**Special Considerations:**
- Should check for existing assignment

### 13. unassign_unit_from_course
**Type:** WRITE
**Tables Accessed:**
- course_learning_unit_assignment (DELETE)
**Special Considerations:**
- Simple delete operation

### 14. get_section_statuses_for_unit_in_course
**Type:** READ (Complex)
**Tables Accessed:**
- unit_section (SELECT)
- course_unit_section_status (SELECT)
**Schema Issues:**
- Nested queries with complex joins
**Special Considerations:**
- Returns sections with their publish status

### 15. publish_section_for_course
**Type:** WRITE
**Tables Accessed:**
- course_unit_section_status (UPDATE)
**Special Considerations:**
- Sets is_published to true

### 16. unpublish_section_for_course
**Type:** WRITE
**Tables Accessed:**
- course_unit_section_status (UPDATE)
**Special Considerations:**
- Sets is_published to false

### 17. get_user_course_ids
**Type:** READ
**Tables Accessed:**
- course_student (SELECT)
**Special Considerations:**
- Returns only course IDs
- Used internally by other functions

### 18. get_student_courses
**Type:** READ
**Tables Accessed:**
- course_student (SELECT)
- course (JOIN)
**Special Considerations:**
- Returns full course details for a student

### 19. get_published_section_details_for_student
**Type:** READ (Very Complex)
**Tables Accessed:**
- unit_section (SELECT)
- course_unit_section_status (JOIN)
- all_regular_tasks (SELECT)
- all_mastery_tasks (SELECT)
- submission (SELECT)
**Schema Issues:**
- Multiple nested queries
- Complex task retrieval logic
**Special Considerations:**
- Most complex query in the codebase
- Retrieves sections with tasks and submission status
- Handles both regular and mastery tasks

### 20. create_submission
**Type:** WRITE (Complex)
**Tables Accessed:**
- all_regular_tasks (SELECT)
- all_mastery_tasks (SELECT)
- submission (SELECT, INSERT)
**Schema Issues:**
- Task type detection logic
- Attempt counting
**Special Considerations:**
- Validates max attempts
- Determines task type dynamically

### 21. get_submission_history
**Type:** READ
**Tables Accessed:**
- submission (SELECT)
**Special Considerations:**
- Simple query with ordering

### 22. get_remaining_attempts
**Type:** READ
**Tables Accessed:**
- all_regular_tasks (SELECT)
- submission (SELECT)
**Special Considerations:**
- Calculates remaining attempts
- Returns null for mastery tasks

### 23. get_task_details
**Type:** READ
**Tables Accessed:**
- all_regular_tasks OR all_mastery_tasks (SELECT)
**Schema Issues:**
- Tries regular first, then mastery
**Special Considerations:**
- Could be simplified with a view

### 24. update_submission_ai_results
**Type:** WRITE
**Tables Accessed:**
- submission (UPDATE)
**Special Considerations:**
- Updates AI feedback fields

### 25. get_submission_by_id
**Type:** READ
**Tables Accessed:**
- submission (SELECT)
**Special Considerations:**
- Simple single-record query

### 26. get_submission_for_task
**Type:** READ
**Tables Accessed:**
- submission (SELECT)
**Special Considerations:**
- Gets latest submission for student/task

### 27. get_course_students
**Type:** READ
**Tables Accessed:**
- course_student (SELECT)
- profiles (JOIN)
**Schema Issues:**
- Similar to get_students_in_course but with more fields
**Special Considerations:**
- Returns detailed student info

### 28. get_section_tasks
**Type:** READ
**Tables Accessed:**
- Views (based on _get_task_table_name)
**Special Considerations:**
- Uses dynamic table name
- Returns ordered tasks

### 29. _get_submission_status_matrix_cached
**Type:** Internal Helper
**Special Considerations:**
- Cache implementation
- Skip migration

### 30. get_submission_status_matrix
**Type:** READ (Complex)
**Special Considerations:**
- Wrapper around cached/uncached versions
- Delegates to _get_submission_status_matrix_uncached

### 31. _get_submission_status_matrix_uncached
**Type:** READ (Very Complex)
**Tables Accessed:**
- course_student (SELECT)
- unit_section (SELECT)
- all_regular_tasks (SELECT)
- all_mastery_tasks (SELECT)
- submission (SELECT)
**Schema Issues:**
- Most complex query with multiple levels
- Performance critical
**Special Considerations:**
- Builds complete matrix of student/task submissions
- Handles both task types
- Critical for teacher dashboard

### 32. update_submission_teacher_override
**Type:** WRITE
**Tables Accessed:**
- submission (UPDATE)
**Special Considerations:**
- Updates teacher feedback/grade

### 33. get_submissions_for_course_and_unit
**Type:** READ (Complex)
**Tables Accessed:**
- unit_section (SELECT)
- all_regular_tasks (SELECT)
- all_mastery_tasks (SELECT)  
- submission (SELECT)
- profiles (JOIN)
**Special Considerations:**
- Complex joins for teacher view
- Returns all submissions with student info

### 34. update_learning_unit
**Type:** WRITE
**Tables Accessed:**
- learning_unit (UPDATE)
**Special Considerations:**
- Simple title update

### 35. delete_learning_unit
**Type:** WRITE
**Tables Accessed:**
- learning_unit (DELETE)
**Special Considerations:**
- CASCADE handles cleanup

### 36. create_section
**Type:** WRITE
**Tables Accessed:**
- unit_section (INSERT)
**Special Considerations:**
- Creates new section with order

### 37. update_section_materials
**Type:** WRITE
**Tables Accessed:**
- unit_section (UPDATE)
**Special Considerations:**
- Updates materials JSON field

### 38. get_tasks_for_section
**Type:** READ
**Tables Accessed:**
- Dynamic based on _get_task_table_name
**Special Considerations:**
- Returns all task fields

### 39. get_regular_tasks_for_section
**Type:** READ
**Tables Accessed:**
- all_regular_tasks (SELECT)
**Special Considerations:**
- Filters by is_mastery=false

### 40. get_mastery_tasks_for_section
**Type:** READ
**Tables Accessed:**
- all_mastery_tasks (SELECT)
**Special Considerations:**
- Returns mastery tasks only

### 41. create_task
**Type:** WRITE (Router)
**Special Considerations:**
- Delegates to create_task_in_new_structure
- Wrapper function

### 42. update_task
**Type:** WRITE (Router)
**Special Considerations:**
- Delegates to update_task_in_new_structure
- Wrapper function

### 43. delete_task
**Type:** WRITE (Router)
**Special Considerations:**
- Delegates to delete_task_in_new_structure
- Wrapper function

### 44. move_task_up
**Type:** WRITE (Complex)
**Tables Accessed:**
- all_regular_tasks (SELECT, UPDATE)
**Schema Issues:**
- Complex order swapping logic
**Special Considerations:**
- Swaps order_in_section with previous task
- Only works for regular tasks

### 45. move_task_down
**Type:** WRITE (Complex)
**Tables Accessed:**
- all_regular_tasks (SELECT, UPDATE)
**Special Considerations:**
- Similar to move_task_up
- Swaps with next task

### 46. update_course
**Type:** WRITE
**Tables Accessed:**
- course (UPDATE)
**Special Considerations:**
- Simple name update

### 47. delete_course
**Type:** WRITE
**Tables Accessed:**
- course (DELETE)
**Special Considerations:**
- CASCADE handles cleanup

### 48. is_teacher_authorized_for_course
**Type:** READ
**Tables Accessed:**
- course_teacher (SELECT)
**Special Considerations:**
- Authorization check
- Returns boolean

### 49. get_course_by_id
**Type:** READ
**Tables Accessed:**
- course (SELECT)
**Special Considerations:**
- Simple single-record query

### 50. get_mastery_tasks_for_course
**Type:** READ (Complex)
**Tables Accessed:**
- course_learning_unit_assignment (SELECT)
- unit_section (SELECT)
- all_mastery_tasks (SELECT)
**Special Considerations:**
- Multi-level join for all mastery tasks in course

### 51. get_next_due_mastery_task (first version)
**Type:** READ (Complex)
**Tables Accessed:**
- student_mastery_progress (SELECT)
- all_mastery_tasks (SELECT)
**Schema Issues:**
- Complex due date logic
**Special Considerations:**
- Finds next task based on spaced repetition

### 52. get_next_mastery_task_or_unviewed_feedback
**Type:** READ (Complex)
**Special Considerations:**
- Wrapper that combines multiple queries
- Returns either next task or unviewed feedback

### 53. mark_feedback_as_viewed_safe
**Type:** WRITE
**Tables Accessed:**
- submission (UPDATE)
**Special Considerations:**
- Sets feedback_viewed_at timestamp

### 54. save_mastery_submission
**Type:** WRITE
**Tables Accessed:**
- mastery_submission (INSERT)
**Special Considerations:**
- Stores mastery-specific submission

### 55. submit_mastery_answer
**Type:** WRITE (Complex)
**Tables Accessed:**
- submission (INSERT)
- student_mastery_progress (SELECT, INSERT/UPDATE)
**Special Considerations:**
- Creates submission and updates progress
- Handles spaced repetition algorithm

### 56. get_mastery_stats_for_student
**Type:** READ (RPC)
**Special Considerations:**
- Uses RPC get_mastery_summary
- Returns aggregated stats

### 57. _update_mastery_progress
**Type:** WRITE (Internal)
**Tables Accessed:**
- student_mastery_progress (INSERT/UPDATE)
**Special Considerations:**
- Updates spaced repetition parameters

### 58. submit_feedback
**Type:** WRITE
**Tables Accessed:**
- feedback (INSERT)
**Special Considerations:**
- Anonymous feedback submission

### 59. get_all_feedback
**Type:** READ
**Tables Accessed:**
- feedback (SELECT)
**Special Considerations:**
- Admin function to retrieve all feedback

### 60. get_next_due_mastery_task (duplicate)
**Type:** READ
**Special Considerations:**
- Duplicate function name - needs cleanup

### 61. get_mastery_overview_for_teacher
**Type:** READ (Complex)
**Tables Accessed:**
- course_student (SELECT)
- student_mastery_progress (SELECT)
- profiles (JOIN)
**Special Considerations:**
- Teacher view of all students' mastery progress

### 62. get_mastery_progress_summary
**Type:** READ (RPC)
**Special Considerations:**
- Uses RPC get_mastery_summary and get_due_tomorrow_count

### 63. calculate_learning_streak
**Type:** READ
**Tables Accessed:**
- submission (SELECT)
**Special Considerations:**
- Calculates consecutive learning days

## Summary

### Total Functions to Migrate: 56
(Excluding already migrated, helpers, and internal functions)

### By Complexity:
- **Simple (READ/WRITE single table):** 23
- **Medium (joins, multiple tables):** 20
- **Complex (nested queries, transactions):** 13

### By Type:
- **READ:** 32
- **WRITE:** 24

### Critical Functions (High Priority):
1. Task CRUD operations (create/update/delete for both types)
2. get_published_section_details_for_student
3. _get_submission_status_matrix_uncached
4. get_submissions_for_course_and_unit
5. create_submission
6. submit_mastery_answer

### Schema Issues Found:
1. **Dynamic table selection** - Several functions select tables based on role or task type
2. **Complex views** - all_regular_tasks and all_mastery_tasks views need to exist
3. **Task structure** - Split between task_base and specific tables adds complexity
4. **Missing indexes** - Performance critical queries may need optimization
5. **Duplicate function** - get_next_due_mastery_task appears twice