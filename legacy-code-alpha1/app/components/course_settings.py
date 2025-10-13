# app/components/course_settings.py
import streamlit as st
from dateutil import parser
from utils.db_queries import (
    get_course_by_id,
    update_course, 
    delete_course,
    is_teacher_authorized_for_course
)
from utils.course_state import set_selected_course_id


def render_course_settings_tab(course_id: str, teacher_id: str):
    """Rendert die Kurs-Einstellungen im Tab.
    
    Args:
        course_id: ID des ausgewählten Kurses
        teacher_id: ID des aktuellen Lehrers
    """
    # Hole Kursdetails
    course, error = get_course_by_id(course_id)
    if error or not course:
        st.error(f"Fehler beim Laden der Kursdaten: {error}")
        return
    
    # Prüfe Berechtigung
    is_authorized, auth_error = is_teacher_authorized_for_course(teacher_id, course_id)
    
    # Zeige Kurs-Informationen
    st.markdown("### 📊 Kurs-Informationen")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Erstellt am:**")
        created_at = parser.parse(course['created_at'])
        st.write(created_at.strftime("%d.%m.%Y um %H:%M Uhr"))
    
    with col2:
        st.markdown("**Kurs-ID:**")
        st.code(course['id'], language=None)
    
    if not is_authorized:
        st.warning(f"⚠️ {auth_error}")
        st.info("Sie können diesen Kurs einsehen, aber nicht bearbeiten.")
        return
    
    st.divider()
    
    # Kurs umbenennen
    st.markdown("### ✏️ Kurs umbenennen")
    
    with st.form("rename_course_form"):
        new_name = st.text_input(
            "Neuer Kursname",
            value=course['name'],
            placeholder="z.B. Mathematik 7A"
        )
        
        if st.form_submit_button("Umbenennen", type="primary"):
            if new_name and new_name != course['name']:
                success, error = update_course(course_id, new_name)
                if success:
                    st.success("Kurs erfolgreich umbenannt!")
                    st.rerun()
                else:
                    st.error(f"Fehler beim Umbenennen: {error}")
            elif not new_name:
                st.error("Bitte geben Sie einen Kursnamen ein.")
    
    st.divider()
    
    # Kurs löschen
    st.markdown("### 🗑️ Kurs löschen")
    
    with st.expander("⚠️ Gefahrenzone - Kurs unwiderruflich löschen", expanded=False):
        st.warning("""
        **Achtung:** Das Löschen eines Kurses kann nicht rückgängig gemacht werden!
        
        Folgende Daten werden gelöscht:
        - Alle Kurszuweisungen (Schüler und Lehrer)
        - Alle Lerneinheit-Zuweisungen zum Kurs
        - Alle kursspezifischen Einstellungen
        
        Die Lerneinheiten selbst bleiben erhalten und können anderen Kursen zugewiesen werden.
        """)
        
        st.markdown("---")
        st.markdown(f"Geben Sie **{course['name']}** ein, um die Löschung zu bestätigen:")
        
        confirmation = st.text_input("Kursname zur Bestätigung", key="delete_confirmation")
        
        col1, col2, col3 = st.columns([2, 1, 2])
        with col2:
            if st.button("🗑️ Kurs löschen", type="primary", use_container_width=True):
                if confirmation == course['name']:
                    success, error = delete_course(course_id)
                    if success:
                        st.success("Kurs wurde gelöscht.")
                        # Lösche die Kursauswahl aus dem State
                        set_selected_course_id(None)
                        st.rerun()
                    else:
                        st.error(f"Fehler beim Löschen: {error}")
                else:
                    st.error("Der eingegebene Kursname stimmt nicht überein.")