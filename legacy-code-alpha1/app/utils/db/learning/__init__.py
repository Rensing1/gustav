"""Learning-related database functions for HttpOnly Cookie support.

This package contains all learning-related functions for submissions, progress,
and mastery that have been migrated to use the RPC pattern with session-based 
authentication.
"""

# Submission functions
from .submissions import (
    create_submission,
    get_remaining_attempts,
    get_submission_for_task,
    update_submission_ai_results,
    update_submission_teacher_override,
    mark_feedback_as_viewed_safe,
    get_submission_history,
    get_submission_by_id
)

# Progress tracking functions
from .progress import (
    get_submission_status_matrix,
    _get_submission_status_matrix_cached,
    _get_submission_status_matrix_uncached,
    get_submissions_for_course_and_unit,
    calculate_learning_streak
)

# Mastery learning functions
from .mastery import (
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

__all__ = [
    # Submissions
    'create_submission',
    'get_remaining_attempts',
    'get_submission_for_task',
    'update_submission_ai_results',
    'update_submission_teacher_override',
    'mark_feedback_as_viewed_safe',
    'get_submission_history',
    'get_submission_by_id',
    # Progress tracking
    'get_submission_status_matrix',
    '_get_submission_status_matrix_cached',
    '_get_submission_status_matrix_uncached',
    'get_submissions_for_course_and_unit',
    'calculate_learning_streak',
    # Mastery learning
    'get_mastery_tasks_for_course',
    'get_next_due_mastery_task',
    'get_next_mastery_task_or_unviewed_feedback',
    'save_mastery_submission',
    'submit_mastery_answer',
    'get_mastery_stats_for_student',
    'get_mastery_overview_for_teacher',
    'get_mastery_progress_summary',
    '_update_mastery_progress'
]