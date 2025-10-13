# app/utils/course_state.py
import streamlit as st
from typing import Optional, Literal

# Einfache Funktionen für allgemeine Kursauswahl (z.B. für Schüler)
def get_selected_course_id() -> Optional[str]:
    """Gibt die aktuell ausgewählte Kurs-ID zurück."""
    if 'selected_course_id' not in st.session_state:
        st.session_state.selected_course_id = None
    return st.session_state.selected_course_id

def set_selected_course_id(course_id: Optional[str]):
    """Setzt die aktuell ausgewählte Kurs-ID."""
    st.session_state.selected_course_id = course_id

class CourseEditorState:
    """State Management für den Kurse Split-View Editor"""
    
    def __init__(self):
        # Initialisiere Session State Variablen
        if 'course_editor' not in st.session_state:
            st.session_state.course_editor = {
                'selected_course_id': None,
                'active_tab': 'units',  # 'units' oder 'users'
            }
    
    @property
    def selected_course_id(self) -> Optional[str]:
        return st.session_state.course_editor.get('selected_course_id')
    
    @selected_course_id.setter
    def selected_course_id(self, value: Optional[str]):
        st.session_state.course_editor['selected_course_id'] = value
    
    @property
    def active_tab(self) -> Literal['units', 'users']:
        return st.session_state.course_editor.get('active_tab', 'units')
    
    @active_tab.setter
    def active_tab(self, value: Literal['units', 'users']):
        st.session_state.course_editor['active_tab'] = value
    
    def reset(self):
        """Setzt den State zurück"""
        st.session_state.course_editor = {
            'selected_course_id': None,
            'active_tab': 'units',
        }