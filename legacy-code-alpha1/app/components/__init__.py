# app/components/__init__.py
"""UI-Komponenten für die GUSTAV-Anwendung."""

from .unit_header import render_unit_header
from .course_assignment import render_course_assignment_bar
from .detail_editor import render_detail_editor
from .course_sidebar import render_course_sidebar
from .course_units import render_course_units_tab
from .course_users import render_course_users_tab
from .course_settings import render_course_settings_tab

__all__ = [
    'render_unit_header',
    'render_course_assignment_bar',
    'render_detail_editor',
    'render_course_sidebar',
    'render_course_units_tab',
    'render_course_users_tab',
    'render_course_settings_tab'
]