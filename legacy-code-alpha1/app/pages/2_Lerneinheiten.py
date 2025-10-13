# app/pages/2_Lerneinheiten.py
import streamlit as st
from streamlit import session_state as state


from utils.db_queries import (
    get_learning_units_by_creator,
    create_learning_unit,
    get_learning_unit_by_id,
    get_assigned_units_for_course
)
from utils.unit_state import UnitEditorState
from utils.datetime_helpers import parse_iso_datetime, format_date_german
from components import (
    render_unit_header,
    render_course_assignment_bar,
    render_detail_editor
)
from components.ui_components import render_sidebar_with_course_selection

# --- Zugriffskontrolle ---
if 'role' not in state or state.role != 'teacher':
    st.error("Zugriff verweigert. Nur Lehrer können diese Seite sehen.")
    st.stop()

# --- UI Implementierung ---
if 'user' not in state or state.user is None:
    st.warning("Fehler: Kein Benutzer eingeloggt.")
    st.stop()

teacher_id = state.user.id

# Sidebar mit Kurs- und Einheitenauswahl
selected_course, selected_unit, selected_section = render_sidebar_with_course_selection(
    teacher_id,
    show_unit_selection=True,
    show_section_navigation=True
)

st.title("📚 Lerneinheiten")

# Initialisiere View-State
if 'view' not in state:
    state.view = 'overview'
    state.selected_unit_id = None

def set_view(view, unit_id=None):
    """Setzt die aktuelle Ansicht und Unit-ID."""
    state.view = view
    state.selected_unit_id = unit_id
    # Reset editor state when switching units
    if view == 'detail':
        editor_state = UnitEditorState()
        editor_state.reset()

# Wenn eine Einheit in der Sidebar gewählt wurde, direkt zur Detailansicht
if selected_unit and state.view == 'overview':
    set_view('detail', unit_id=selected_unit['id'])
    st.rerun()

# --- Übersichtsansicht ---
if state.view == 'overview':
    if selected_course:
        st.subheader(f"Lerneinheiten im Kurs: {selected_course['name']}")
        # Lade Lerneinheiten des gewählten Kurses
        learning_units, error = get_assigned_units_for_course(selected_course['id'])
        if error:
            st.error(f"Fehler beim Laden der Lerneinheiten: {error}")
            learning_units = []
    else:
        st.subheader("Alle meine Lerneinheiten")
        # Lade alle Lerneinheiten des Lehrers
        learning_units, error = get_learning_units_by_creator(teacher_id)
        if error:
            st.error(f"Fehler beim Laden der Lerneinheiten: {error}")
            learning_units = []
    
    # Grid-Layout für Karten
    cols = st.columns(3)
    
    # Neue Lerneinheit erstellen - Karte
    with cols[0]:
        with st.container(border=True):
            st.markdown("### ➕ Neue Lerneinheit")
            st.caption("Erstellen Sie eine neue Lerneinheit")
            if st.button("Erstellen", key="create_new", use_container_width=True):
                set_view('create_new')
                st.rerun()
    
    # Lerneinheiten-Karten
    for i, unit in enumerate(learning_units):
        col_index = (i + 1) % 3
        with cols[col_index]:
            with st.container(border=True):
                st.markdown(f"### {unit['title']}")
                
                # Zeige Erstellungsdatum (wenn vorhanden)
                if 'created_at' in unit and unit['created_at']:
                    created_at = parse_iso_datetime(unit['created_at'])
                    if created_at:
                        st.caption(f"Erstellt am {format_date_german(created_at)}")
                
                if st.button("Öffnen", key=f"open_{unit['id']}", use_container_width=True):
                    set_view('detail', unit_id=unit['id'])
                    st.rerun()

# --- Neue Lerneinheit erstellen ---
elif state.view == 'create_new':
    st.subheader("Neue Lerneinheit erstellen")
    
    with st.form("new_unit_form"):
        new_unit_title = st.text_input(
            "Titel der neuen Lerneinheit",
            placeholder="z.B. Mathematik Grundlagen"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            cancel = st.form_submit_button("Abbrechen", use_container_width=True)
        with col2:
            submit = st.form_submit_button("Erstellen", type="primary", use_container_width=True)
        
        if cancel:
            set_view('overview')
            st.rerun()
        
        if submit:
            if not new_unit_title.strip():
                st.error("Der Titel darf nicht leer sein.")
            else:
                new_unit, error = create_learning_unit(new_unit_title.strip(), teacher_id)
                if error:
                    st.error(f"Fehler beim Erstellen: {error}")
                else:
                    st.success("Lerneinheit erstellt!")
                    # Direkt zur Detailansicht wechseln
                    set_view('detail', unit_id=new_unit['id'])
                    st.rerun()

# --- Detailansicht mit Split-View ---
elif state.view == 'detail':
    if not state.selected_unit_id:
        st.error("Keine Lerneinheit ausgewählt.")
        if st.button("Zurück zur Übersicht"):
            set_view('overview')
            st.rerun()
        st.stop()
    
    # Lade Lerneinheit-Details
    unit, error = get_learning_unit_by_id(state.selected_unit_id)
    if error or not unit:
        st.error(f"Fehler beim Laden der Lerneinheit: {error}")
        if st.button("Zurück zur Übersicht"):
            set_view('overview')
            st.rerun()
        st.stop()
    
    # Header mit Aktionen
    go_back = render_unit_header(unit['id'], unit['title'])
    if go_back:
        set_view('overview')
        st.rerun()
    
    # Kurszuweisungs-Leiste
    render_course_assignment_bar(unit['id'], teacher_id)
    
    # Trennlinie
    st.divider()
    
    # Quick Actions Bar (wenn Abschnitt ausgewählt)
    if selected_section:
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("➕ 📄 Neues Material", use_container_width=True):
                state.selected_section_id = selected_section['id']
                state.creating_type = 'material'
                st.rerun()
        with col2:
            if st.button("➕ ✏️ Neue Aufgabe", use_container_width=True):
                state.selected_section_id = selected_section['id']
                state.creating_type = 'task'
                st.rerun()
        with col3:
            if st.button("➕ 🎯 Neuer Wissensfestiger", use_container_width=True):
                state.selected_section_id = selected_section['id']
                state.creating_type = 'mastery'
                st.rerun()
        st.divider()
    
    # Detail-Editor mit voller Breite
    render_detail_editor(unit['id'])

# --- Fallback ---
else:
    st.error(f"Unbekannte Ansicht: {state.view}")
    if st.button("Zurück zur Übersicht"):
        set_view('overview')
        st.rerun()