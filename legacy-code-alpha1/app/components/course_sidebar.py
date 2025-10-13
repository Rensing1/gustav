# app/components/course_sidebar.py
import streamlit as st
from utils.db_queries import get_courses_by_creator, create_course
from utils.course_state import CourseEditorState

def render_course_sidebar(teacher_id: str):
    """Rendert die Kursliste in der linken Spalte.
    
    Args:
        teacher_id: ID des aktuellen Lehrers
    """
    state = CourseEditorState()
    
    # Header
    st.markdown("### MEINE KURSE")
    
    # Lade Kurse
    courses, error = get_courses_by_creator(teacher_id)
    if error:
        st.error(f"Fehler beim Laden: {error}")
        courses = []
    
    # Kursliste
    if courses:
        for course in courses:
            # Button für jeden Kurs
            is_selected = state.selected_course_id == course['id']
            
            # Verwende verschiedene Styles für ausgewählten Kurs
            if is_selected:
                if st.button(
                    f"▶ **{course['name']}**",
                    key=f"course_{course['id']}",
                    use_container_width=True,
                    type="primary"
                ):
                    # Bereits ausgewählt, nichts tun
                    pass
            else:
                if st.button(
                    f"📚 {course['name']}",
                    key=f"course_{course['id']}",
                    use_container_width=True
                ):
                    state.selected_course_id = course['id']
                    st.rerun()
    else:
        st.info("Noch keine Kurse vorhanden.")
    
    # Divider
    st.divider()
    
    # Neuer Kurs Button
    with st.popover("➕ Neuer Kurs", use_container_width=True):
        render_new_course_form(teacher_id)

def render_new_course_form(teacher_id: str):
    """Rendert das Formular für einen neuen Kurs.
    
    Args:
        teacher_id: ID des Lehrers
    """
    st.markdown("### Neuen Kurs erstellen")
    
    with st.form("new_course_form", clear_on_submit=True):
        course_name = st.text_input(
            "Kursname",
            placeholder="z.B. Mathematik 7A"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            cancel = st.form_submit_button("Abbrechen", use_container_width=True)
        with col2:
            create = st.form_submit_button("Erstellen", type="primary", use_container_width=True)
        
        if create and course_name:
            new_course, error = create_course(course_name.strip(), teacher_id)
            if error:
                st.error(f"Fehler beim Erstellen: {error}")
            else:
                st.success("Kurs erstellt!")
                # Wähle den neuen Kurs aus
                state = CourseEditorState()
                state.selected_course_id = new_course['id']
                st.rerun()
        elif create:
            st.error("Bitte geben Sie einen Kursnamen ein.")