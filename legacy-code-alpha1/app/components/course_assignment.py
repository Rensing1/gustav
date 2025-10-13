# app/components/course_assignment.py
import streamlit as st
from utils.db_queries import (
    get_courses_assigned_to_unit,
    get_courses_by_creator,
    assign_unit_to_course,
    unassign_unit_from_course
)

def render_course_assignment_bar(unit_id: str, teacher_id: str):
    """Rendert die Kurszuweisungs-Leiste unterhalb des Headers.
    
    Args:
        unit_id: ID der Lerneinheit
        teacher_id: ID des Lehrers
    """
    # Container für die Kurszuweisungs-Leiste
    with st.container():
        col1, col2 = st.columns([5, 1])
        
        # Hole zugewiesene Kurse
        assigned_courses, error = get_courses_assigned_to_unit(unit_id)
        if error:
            st.error(f"Fehler beim Laden der Kurszuweisungen: {error}")
            return
        
        # Linke Spalte: Anzeige der zugewiesenen Kurse
        with col1:
            if assigned_courses:
                course_names = [c['name'] or 'Unbenannter Kurs' for c in assigned_courses]
                courses_text = ", ".join(course_names)
                st.caption(f"**Zugewiesen an:** {courses_text}")
            else:
                st.caption("**Zugewiesen an:** _Keine Kurse_")
        
        # Rechte Spalte: Button zum Verwalten der Zuweisungen
        with col2:
            with st.popover("+ Kurs zuweisen", use_container_width=True):
                render_course_assignment_modal(unit_id, teacher_id, assigned_courses)

def render_course_assignment_modal(unit_id: str, teacher_id: str, currently_assigned: list):
    """Rendert das Modal für die Kursverwaltung.
    
    Args:
        unit_id: ID der Lerneinheit
        teacher_id: ID des Lehrers
        currently_assigned: Liste der aktuell zugewiesenen Kurse
    """
    st.markdown("### Kurszuweisungen verwalten")
    
    # Hole alle Kurse des Lehrers
    all_courses, error = get_courses_by_creator(teacher_id)
    if error:
        st.error(f"Fehler beim Laden der Kurse: {error}")
        return
    
    if not all_courses:
        st.info("Sie haben noch keine Kurse erstellt.")
        st.caption("Erstellen Sie zuerst einen Kurs auf der Kurse-Seite.")
        return
    
    # Erstelle Mapping für schnellen Zugriff (mit None-Filterung)
    assigned_ids = {c['id'] for c in currently_assigned if c.get('id') is not None}
    course_map = {c['id']: c['name'] for c in all_courses if c.get('id') is not None}
    
    # Filtere assigned_ids um nur existierende Kurse zu behalten
    valid_assigned_ids = [course_id for course_id in assigned_ids if course_id in course_map]
    
    # Multiselect für Kurszuweisungen
    selected_ids = st.multiselect(
        "Wählen Sie die Kurse aus:",
        options=list(course_map.keys()),
        default=valid_assigned_ids,
        format_func=lambda x: course_map.get(x, "Unbekannter Kurs"),
        key=f"course_select_{unit_id}"
    )
    
    # Speichern-Button
    col1, col2 = st.columns(2)
    with col1:
        cancel = st.button("Abbrechen", key=f"cancel_courses_{unit_id}", use_container_width=True)
    with col2:
        save = st.button("Speichern", type="primary", key=f"save_courses_{unit_id}", use_container_width=True)
    
    if save:
        # Berechne Änderungen
        new_ids = set(selected_ids)
        ids_to_add = new_ids - assigned_ids
        ids_to_remove = assigned_ids - new_ids
        
        success = True
        
        # Füge neue Zuweisungen hinzu
        for course_id in ids_to_add:
            result, error = assign_unit_to_course(unit_id, course_id)
            if error:
                st.error(f"Fehler beim Zuweisen zu {course_map.get(course_id, 'Kurs')}: {error}")
                success = False
        
        # Entferne alte Zuweisungen
        for course_id in ids_to_remove:
            result, error = unassign_unit_from_course(unit_id, course_id)
            if error:
                st.error(f"Fehler beim Entfernen von {course_map.get(course_id, 'Kurs')}: {error}")
                success = False
        
        if success:
            st.success("Kurszuweisungen aktualisiert!")
            st.rerun()
    
    # Zeige Änderungsvorschau
    if not cancel and not save:
        new_ids = set(selected_ids)
        ids_to_add = new_ids - assigned_ids
        ids_to_remove = assigned_ids - new_ids
        
        if ids_to_add or ids_to_remove:
            st.divider()
            st.caption("**Änderungen:**")
            if ids_to_add:
                for cid in ids_to_add:
                    st.caption(f"➕ {course_map.get(cid, 'Unbekannt')} wird hinzugefügt")
            if ids_to_remove:
                for cid in ids_to_remove:
                    st.caption(f"➖ {course_map.get(cid, 'Unbekannt')} wird entfernt")