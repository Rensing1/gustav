"""
Database utilities module.
Re-exports session functions for backwards compatibility.
"""

from .core.session import get_session_id, get_anon_client, handle_rpc_result
from .core.auth import get_users_by_role, is_teacher_authorized_for_course
# Learning management functions
from .learning import (
    create_submission,
    get_remaining_attempts, 
    get_submission_for_task,
    update_submission_ai_results,
    update_submission_teacher_override,
    mark_feedback_as_viewed_safe,
    get_submission_history,
    get_submission_by_id,
    # Progress tracking
    get_submission_status_matrix,
    _get_submission_status_matrix_cached,
    _get_submission_status_matrix_uncached,
    get_submissions_for_course_and_unit,
    calculate_learning_streak,
    # Mastery learning
    get_mastery_tasks_for_course,
    get_next_due_mastery_task,
    get_next_mastery_task_or_unviewed_feedback,
    save_mastery_submission,
    submit_mastery_answer,
    get_mastery_stats_for_student,
    get_mastery_overview_for_teacher,
    get_mastery_progress_summary,
    _update_mastery_progress
)
# Course management functions
from .courses import (
    get_courses_by_creator,
    create_course,
    get_students_in_course,
    get_teachers_in_course,
    add_user_to_course,
    remove_user_from_course,
    get_courses_assigned_to_unit,
    assign_unit_to_course,
    unassign_unit_from_course,
    get_assigned_units_for_course,
    get_section_statuses_for_unit_in_course,
    update_course,
    delete_course,
    get_course_by_id,
    # Enrollment functions
    get_user_course_ids,
    get_student_courses,
    get_course_students,
    get_published_section_details_for_student
)
# Content management functions
from .content import (
    # Units
    get_learning_units_by_creator,
    create_learning_unit,
    update_learning_unit,
    delete_learning_unit,
    get_learning_unit_by_id,
    # Sections
    create_section,
    get_sections_for_unit,
    update_section_materials,
    # Tasks
    create_regular_task,
    create_mastery_task,
    update_task_in_new_structure,
    delete_task_in_new_structure,
    get_tasks_for_section,
    get_regular_tasks_for_section,
    get_mastery_tasks_for_section,
    get_section_tasks,
    get_task_details,
    move_task_up,
    move_task_down,
    # Helper functions
    _get_task_table_name,
    get_regular_tasks_table_name,
    get_mastery_tasks_table_name,
    # Legacy
    create_task_in_new_structure
)
# Platform functions
from .platform import (
    submit_feedback,
    get_all_feedback
)

__all__ = [
    # Session helpers
    'get_session_id', 
    'get_anon_client', 
    'handle_rpc_result',
    # Authentication
    'get_users_by_role',
    'is_teacher_authorized_for_course',
    # Submission functions
    'create_submission',
    'get_remaining_attempts',
    'get_submission_for_task', 
    'update_submission_ai_results',
    'update_submission_teacher_override',
    'mark_feedback_as_viewed_safe',
    'get_submission_history',
    'get_submission_by_id',
    # Progress tracking functions
    'get_submission_status_matrix',
    '_get_submission_status_matrix_cached',
    '_get_submission_status_matrix_uncached',
    'get_submissions_for_course_and_unit',
    'calculate_learning_streak',
    # Mastery learning functions
    'get_mastery_tasks_for_course',
    'get_next_due_mastery_task',
    'get_next_mastery_task_or_unviewed_feedback',
    'save_mastery_submission',
    'submit_mastery_answer',
    'get_mastery_stats_for_student',
    'get_mastery_overview_for_teacher',
    'get_mastery_progress_summary',
    '_update_mastery_progress',
    # Course management functions
    'get_courses_by_creator',
    'create_course',
    'get_students_in_course',
    'get_teachers_in_course',
    'add_user_to_course',
    'remove_user_from_course',
    'get_courses_assigned_to_unit',
    'assign_unit_to_course',
    'unassign_unit_from_course',
    'get_assigned_units_for_course',
    'get_section_statuses_for_unit_in_course',
    'update_course',
    'delete_course',
    'get_course_by_id',
    # Course enrollment functions
    'get_user_course_ids',
    'get_student_courses',
    'get_course_students',
    'get_published_section_details_for_student',
    # Content - Units
    'get_learning_units_by_creator',
    'create_learning_unit',
    'update_learning_unit',
    'delete_learning_unit',
    'get_learning_unit_by_id',
    # Content - Sections
    'create_section',
    'get_sections_for_unit',
    'update_section_materials',
    # Content - Tasks
    'create_regular_task',
    'create_mastery_task',
    'update_task_in_new_structure',
    'delete_task_in_new_structure',
    'get_tasks_for_section',
    'get_regular_tasks_for_section',
    'get_mastery_tasks_for_section',
    'get_section_tasks',
    'get_task_details',
    'move_task_up',
    'move_task_down',
    # Helper functions
    '_get_task_table_name',
    'get_regular_tasks_table_name',
    'get_mastery_tasks_table_name',
    # Legacy
    'create_task_in_new_structure',
    # Platform functions
    'submit_feedback',
    'get_all_feedback'
]