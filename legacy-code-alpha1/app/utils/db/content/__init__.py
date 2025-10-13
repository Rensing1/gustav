"""Content-related database functions for HttpOnly Cookie support.

This package contains all content management functions for learning units,
sections, and tasks that have been migrated to use the RPC pattern with 
session-based authentication.
"""

# Learning unit functions
from .units import (
    get_learning_units_by_creator,
    create_learning_unit,
    update_learning_unit,
    delete_learning_unit,
    get_learning_unit_by_id
)

# Section functions
from .sections import (
    create_section,
    get_sections_for_unit,
    update_section_materials
)

# Task functions
from .tasks import (
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
    # Legacy wrapper
    create_task_in_new_structure
)

__all__ = [
    # Units
    'get_learning_units_by_creator',
    'create_learning_unit',
    'update_learning_unit',
    'delete_learning_unit',
    'get_learning_unit_by_id',
    # Sections
    'create_section',
    'get_sections_for_unit',
    'update_section_materials',
    # Tasks
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
    'create_task_in_new_structure'
]