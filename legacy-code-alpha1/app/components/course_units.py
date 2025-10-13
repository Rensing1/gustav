# app/components/course_units.py
import streamlit as st
from utils.db_queries import (
    get_assigned_units_for_course,
    get_learning_units_by_creator,
    assign_unit_to_course,
    unassign_unit_from_course
)

def render_course_units_tab(course_id: str, course_name: str, teacher_id: str):
    """Rendert den Tab für Lerneinheiten-Zuweisung.
    
    Args:
        course_id: ID des ausgewählten Kurses
        course_name: Name des Kurses
        teacher_id: ID des Lehrers
    """
    # Lade zugewiesene Lerneinheiten
    assigned_units, error = get_assigned_units_for_course(course_id)
    if error:
        st.error(f"Fehler beim Laden der Lerneinheiten: {error}")
        assigned_units = []
    
    # Zeige zugewiesene Lerneinheiten
    st.markdown("#### Zugewiesene Lerneinheiten")
    
    if assigned_units:
        # Liste der zugewiesenen Einheiten mit Entfernen-Option
        for unit in assigned_units:
            col1, col2 = st.columns([10, 1])
            
            with col1:
                st.markdown(f"📖 {unit.get('title', 'Unbenannt')}")
            
            with col2:
                if st.button("🗑️", key=f"remove_unit_{unit['id']}", help="Zuweisung entfernen"):
                    success, error = unassign_unit_from_course(unit['id'], course_id)
                    if success:
                        st.success("Zuweisung entfernt!")
                        st.rerun()
                    else:
                        st.error(error or "Fehler beim Entfernen")
    else:
        st.info("Diesem Kurs sind noch keine Lerneinheiten zugewiesen.")
    
    # Divider
    st.divider()
    
    # Neue Lerneinheiten zuweisen
    st.markdown("#### Lerneinheiten hinzufügen")
    
    # Lade alle Lerneinheiten des Lehrers
    all_units, error = get_learning_units_by_creator(teacher_id)
    if error:
        st.error(f"Fehler beim Laden der verfügbaren Lerneinheiten: {error}")
        return
    
    if not all_units:
        st.info("Sie haben noch keine Lerneinheiten erstellt.")
        st.caption("Erstellen Sie zuerst Lerneinheiten auf der Lerneinheiten-Seite.")
        return
    
    # Filtere bereits zugewiesene Einheiten
    assigned_ids = {unit['id'] for unit in assigned_units}
    available_units = [unit for unit in all_units if unit['id'] not in assigned_ids]
    
    if not available_units:
        st.info("Alle Ihre Lerneinheiten sind bereits diesem Kurs zugewiesen.")
        return
    
    # Multiselect für Zuweisung
    with st.form(f"assign_units_form_{course_id}"):
        # Erstelle Options-Dictionary
        unit_options = {unit['id']: unit['title'] for unit in available_units}
        
        selected_unit_ids = st.multiselect(
            "Wählen Sie Lerneinheiten aus:",
            options=list(unit_options.keys()),
            format_func=lambda x: unit_options.get(x, "Unbekannt"),
            help="Sie können mehrere Lerneinheiten gleichzeitig auswählen"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            cancel = st.form_submit_button("Abbrechen", use_container_width=True)
        with col2:
            assign = st.form_submit_button("Zuweisen", type="primary", use_container_width=True)
        
        if assign and selected_unit_ids:
            # Weise alle ausgewählten Einheiten zu
            success_count = 0
            errors = []
            
            for unit_id in selected_unit_ids:
                success, error = assign_unit_to_course(unit_id, course_id)
                if success:
                    success_count += 1
                elif error:
                    errors.append(f"{unit_options.get(unit_id, 'Unbekannt')}: {error}")
            
            # Feedback
            if success_count > 0:
                st.success(f"{success_count} Lerneinheit(en) erfolgreich zugewiesen!")
            
            for error_msg in errors:
                st.error(error_msg)
            
            if success_count > 0:
                st.rerun()
        elif assign:
            st.warning("Bitte wählen Sie mindestens eine Lerneinheit aus.")