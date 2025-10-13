"""Course-related database functions for HttpOnly Cookie support.

This package contains all course management and enrollment functions
that have been migrated to use the RPC pattern with session-based authentication.
"""

# Course management functions
from .management import (
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
    get_course_by_id
)

# Course enrollment functions
from .enrollment import (
    get_user_course_ids,
    get_student_courses,
    get_course_students,
    get_published_section_details_for_student
)

__all__ = [
    # Management functions
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
    # Enrollment functions
    'get_user_course_ids',
    'get_student_courses',
    'get_course_students',
    'get_published_section_details_for_student'
]