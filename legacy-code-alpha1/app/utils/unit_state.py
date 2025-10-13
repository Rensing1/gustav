# app/utils/unit_state.py
import streamlit as st
from typing import Dict, Set, Optional, Literal

# Einfache Funktionen für allgemeine Unit-Auswahl (analog zu course_state.py)
def get_selected_unit_id() -> Optional[str]:
    """Gibt die aktuell ausgewählte Unit-ID zurück."""
    if 'selected_unit_id' not in st.session_state:
        st.session_state.selected_unit_id = None
    return st.session_state.selected_unit_id

def set_selected_unit_id(unit_id: Optional[str]):
    """Setzt die aktuell ausgewählte Unit-ID."""
    st.session_state.selected_unit_id = unit_id

class UnitEditorState:
    """State Management für den Split-View Editor der Lerneinheiten"""
    
    def __init__(self):
        # Initialisiere Session State Variablen
        if 'unit_editor' not in st.session_state:
            st.session_state.unit_editor = {
                'selected_item': None,  # {type: 'section'|'material'|'task', id: str, section_id: str}
                'expanded_sections': set(),  # IDs der aufgeklappten Abschnitte
                'edit_mode': False,
                'editing_item': None,  # Item das gerade bearbeitet wird
                'unsaved_changes': False,
                'view_mode': 'split',  # 'split' oder 'fullscreen'
            }
    
    @property
    def selected_item(self) -> Optional[Dict]:
        return st.session_state.unit_editor.get('selected_item')
    
    @selected_item.setter
    def selected_item(self, value: Optional[Dict]):
        st.session_state.unit_editor['selected_item'] = value
        # Wenn ein Item ausgewählt wird, stelle sicher dass die Section aufgeklappt ist
        if value and value.get('section_id'):
            self.expand_section(value['section_id'])
    
    @property
    def expanded_sections(self) -> Set[str]:
        return st.session_state.unit_editor.get('expanded_sections', set())
    
    def toggle_section(self, section_id: str):
        """Klappt eine Section auf oder zu"""
        sections = st.session_state.unit_editor.get('expanded_sections', set())
        if section_id in sections:
            sections.remove(section_id)
        else:
            sections.add(section_id)
        st.session_state.unit_editor['expanded_sections'] = sections
    
    def expand_section(self, section_id: str):
        """Klappt eine Section auf"""
        sections = st.session_state.unit_editor.get('expanded_sections', set())
        sections.add(section_id)
        st.session_state.unit_editor['expanded_sections'] = sections
    
    def collapse_section(self, section_id: str):
        """Klappt eine Section zu"""
        sections = st.session_state.unit_editor.get('expanded_sections', set())
        sections.discard(section_id)
        st.session_state.unit_editor['expanded_sections'] = sections
    
    @property
    def edit_mode(self) -> bool:
        return st.session_state.unit_editor.get('edit_mode', False)
    
    @edit_mode.setter
    def edit_mode(self, value: bool):
        st.session_state.unit_editor['edit_mode'] = value
        if not value:
            # Beim Verlassen des Edit-Modus, lösche das editing_item
            st.session_state.unit_editor['editing_item'] = None
    
    @property
    def editing_item(self) -> Optional[Dict]:
        return st.session_state.unit_editor.get('editing_item')
    
    @editing_item.setter
    def editing_item(self, value: Optional[Dict]):
        st.session_state.unit_editor['editing_item'] = value
        if value:
            st.session_state.unit_editor['edit_mode'] = True
    
    def is_editing(self, item_type: str, item_id: str) -> bool:
        """Prüft ob ein bestimmtes Item gerade bearbeitet wird"""
        editing = self.editing_item
        return (editing and 
                editing.get('type') == item_type and 
                editing.get('id') == item_id)
    
    def start_editing(self, item_type: str, item_id: str, section_id: Optional[str] = None):
        """Startet die Bearbeitung eines Items"""
        self.editing_item = {
            'type': item_type,
            'id': item_id,
            'section_id': section_id
        }
    
    def stop_editing(self):
        """Beendet die Bearbeitung"""
        self.edit_mode = False
    
    @property
    def unsaved_changes(self) -> bool:
        return st.session_state.unit_editor.get('unsaved_changes', False)
    
    @unsaved_changes.setter
    def unsaved_changes(self, value: bool):
        st.session_state.unit_editor['unsaved_changes'] = value
    
    def reset(self):
        """Setzt den State zurück"""
        st.session_state.unit_editor = {
            'selected_item': None,
            'expanded_sections': set(),
            'edit_mode': False,
            'editing_item': None,
            'unsaved_changes': False,
            'view_mode': 'split',
        }
    
    def expand_all(self):
        """Klappt alle Sections auf"""
        # Diese Methode muss die section_ids kennen, wird vom Aufrufer befüllt
        pass
    
    def collapse_all(self):
        """Klappt alle Sections zu"""
        st.session_state.unit_editor['expanded_sections'] = set()