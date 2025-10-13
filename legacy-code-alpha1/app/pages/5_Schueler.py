import streamlit as st
from streamlit import session_state as state

# Seitenkonfiguration


# Importiere UI-Komponenten und DB-Funktionen
from components.ui_components import render_sidebar_with_course_selection
from utils.db_queries import get_students_in_course

# --- Zugriffskontrolle ---
if 'role' not in state or state.role != 'teacher':
    st.error("Zugriff verweigert. Nur Lehrer können die Schülerübersicht sehen.")
    st.stop()

if 'user' not in state or state.user is None:
    st.warning("Fehler: Kein Benutzer eingeloggt.")
    st.stop()

teacher_id = state.user.id

# --- Sidebar mit Kursauswahl ---
selected_course, _, _ = render_sidebar_with_course_selection(
    teacher_id,
    show_unit_selection=False  # Keine Einheitenauswahl für Schülerübersicht
)

# --- Seitenkonfiguration und Titel ---
st.title("👥 Schülerübersicht")
st.markdown("Hier können Sie die Schüler in Ihren Kursen verwalten und ihre Fortschritte einsehen.")

# --- Hauptinhalt ---
if selected_course:
    st.subheader(f"Schüler im Kurs: {selected_course['name']}")
    
    # Lade Schüler des Kurses
    students, error = get_students_in_course(selected_course['id'])
    
    if error:
        st.error(f"Fehler beim Laden der Schüler: {error}")
    elif not students:
        st.info("ℹ️ In diesem Kurs sind noch keine Schüler eingeschrieben.")
    else:
        # Zeige Schüleranzahl
        st.metric("Anzahl Schüler", len(students))
        
        # Tabelle mit Schülern
        st.markdown("### Eingeschriebene Schüler")
        
        # Erstelle eine einfache Tabelle
        for i, student in enumerate(students, 1):
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    # Zeige E-Mail und ID
                    st.markdown(f"**{i}. {student.get('email', 'Unbekannt')}**")
                    st.caption(f"ID: {student.get('id', 'N/A')}")
                
                with col2:
                    # Placeholder für zukünftige Aktionen
                    st.button(
                        "Details anzeigen",
                        key=f"details_{student.get('id')}",
                        disabled=True,
                        help="Diese Funktion ist noch in Entwicklung"
                    )
        
        # Hinweis auf Live-Unterricht
        st.info(
            "💡 **Tipp**: Nutzen Sie die **Live-Unterricht** Ansicht, um die aktuellen "
            "Einreichungen und Fortschritte der Schüler in Echtzeit zu verfolgen."
        )
else:
    # Kein Kurs ausgewählt
    st.info("ℹ️ Bitte wählen Sie einen Kurs in der Sidebar aus, um die Schülerübersicht zu sehen.")
    
    # Hilfreiche Informationen
    with st.expander("ℹ️ So funktioniert die Schülerübersicht"):
        st.markdown("""
        **Schüler verwalten:**
        1. Wählen Sie einen Kurs in der Sidebar aus
        2. Sehen Sie alle eingeschriebenen Schüler
        3. (Zukünftig) Verwalten Sie individuelle Fortschritte
        
        **Aktuelle Möglichkeiten:**
        - Übersicht aller Schüler pro Kurs
        - Basis für zukünftige Detailansichten
        
        **Empfehlung:**
        Nutzen Sie aktuell die **Live-Unterricht** Ansicht für:
        - Echtzeit-Überwachung von Einreichungen
        - Bewertung von Schülerarbeiten
        - Feedback-Überschreibung
        """)