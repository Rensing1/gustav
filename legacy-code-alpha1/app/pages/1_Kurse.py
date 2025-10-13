# app/pages/1_Kurse.py
import streamlit as st
from streamlit import session_state as state

# Seitenkonfiguration

from utils.db_queries import get_course_by_id
from utils.course_state import CourseEditorState
from components import (
    render_course_sidebar,
    render_course_units_tab,
    render_course_users_tab,
    render_course_settings_tab
)
from components.ui_components import render_sidebar_with_course_selection

# --- Zugriffskontrolle ---
if 'role' not in state or state.role != 'teacher':
    st.error("Zugriff verweigert. Nur Lehrer können Kurse verwalten.")
    st.stop()

# --- Seitenkonfiguration und Titel ---
st.title("🏫 Kurse verwalten")

# --- Hauptbereich ---
if 'user' not in state or state.user is None:
    st.warning("Fehler: Kein Benutzer eingeloggt.")
    st.stop()

teacher_id = state.user.id

# Sidebar mit Kursauswahl
selected_course, _, _ = render_sidebar_with_course_selection(
    teacher_id,
    show_unit_selection=False
)

# Initialisiere Course State
course_state = CourseEditorState()

# Hauptbereich
if selected_course:
    # Header mit Kursname
    st.markdown(f"## {selected_course['name']}")
    
    # Tabs für verschiedene Funktionen
    tab1, tab2, tab3 = st.tabs(["📚 Lerneinheiten", "👥 Nutzer", "🛠️ Kurs-Einstellungen"])
    
    with tab1:
        render_course_units_tab(
            course_id=selected_course['id'],
            course_name=selected_course['name'],
            teacher_id=teacher_id
        )
    
    with tab2:
        render_course_users_tab(
            course_id=selected_course['id'],
            course_name=selected_course['name'],
            current_teacher_id=teacher_id
        )
    
    with tab3:
        # Kurs-Einstellungen
        render_course_settings_tab(
            course_id=selected_course['id'],
            teacher_id=teacher_id
        )
else:
    # Leerer Zustand - Benutzerfreundliche Kurserstellung
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### 🎯 Willkommen bei der Kursverwaltung!")
        st.markdown("")
        
        # Prüfe ob es wirklich keine Kurse gibt
        from utils.db_queries import get_courses_by_creator
        courses, _ = get_courses_by_creator(teacher_id)
        
        if not courses:
            st.info("Sie haben noch keine Kurse erstellt. Legen Sie Ihren ersten Kurs an, um zu beginnen!")
        else:
            st.info("👈 Wählen Sie einen Kurs in der Sidebar aus")
        
        st.markdown("")
        
        # Kurserstellungs-Button und Formular
        if st.button("➕ Neuen Kurs erstellen", type="primary", use_container_width=True):
            st.session_state.show_course_form = True
        
        # Inline-Formular für Kurserstellung
        if st.session_state.get('show_course_form', False):
            st.markdown("---")
            with st.form("new_course_form", clear_on_submit=True):
                st.markdown("#### Neuer Kurs")
                course_name = st.text_input(
                    "Kursname",
                    placeholder="z.B. Mathematik 7A",
                    help="Geben Sie einen aussagekräftigen Namen für Ihren Kurs ein"
                )
                
                col_cancel, col_create = st.columns(2)
                with col_cancel:
                    if st.form_submit_button("Abbrechen", use_container_width=True):
                        st.session_state.show_course_form = False
                        st.rerun()
                
                with col_create:
                    if st.form_submit_button("Kurs erstellen", type="primary", use_container_width=True):
                        if course_name and course_name.strip():
                            from utils.db_queries import create_course
                            new_course, error = create_course(course_name.strip(), teacher_id)
                            if error:
                                st.error(f"Fehler beim Erstellen: {error}")
                            else:
                                st.success("Kurs erfolgreich erstellt!")
                                # Setze den neuen Kurs als ausgewählt
                                from utils.course_state import set_selected_course_id
                                set_selected_course_id(new_course['id'])
                                st.session_state.show_course_form = False
                                st.rerun()
                        else:
                            st.error("Bitte geben Sie einen Kursnamen ein.")
        
        # Hilfreiche Informationen
        st.markdown("")
        st.markdown("")
        with st.expander("ℹ️ So funktioniert die Kursverwaltung"):
            st.markdown("""
            **Kurse verwalten:**
            - Erstellen Sie neue Kurse mit dem Button oben
            - Wählen Sie einen Kurs in der Sidebar aus
            - Weisen Sie Lerneinheiten zu
            - Verwalten Sie Schüler und Lehrer
            
            **Lerneinheiten:**
            - Erstellen Sie zuerst Lerneinheiten auf der Lerneinheiten-Seite
            - Weisen Sie diese dann Ihren Kursen zu
            - Eine Lerneinheit kann mehreren Kursen zugewiesen werden
            
            **Nutzerverwaltung:**
            - Fügen Sie Schüler zu Ihren Kursen hinzu
            - Laden Sie andere Lehrer zur Zusammenarbeit ein
            """)