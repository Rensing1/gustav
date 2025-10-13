# app/components/unit_header.py
import streamlit as st
from utils.db_queries import update_learning_unit, delete_learning_unit
from utils.unit_state import UnitEditorState

def render_unit_header(unit_id: str, unit_title: str) -> bool:
    """Rendert den Header für die Lerneinheiten-Detailansicht.
    
    Args:
        unit_id: ID der Lerneinheit
        unit_title: Aktueller Titel der Lerneinheit
        
    Returns:
        bool: True wenn zur Übersicht navigiert werden soll
    """
    # Header-Layout mit 3 Spalten
    col1, col2, col3 = st.columns([1, 4, 2])
    
    # Linke Spalte: Zurück-Button
    with col1:
        if st.button("← Zurück", key="back_to_overview"):
            return True
    
    # Mittlere Spalte: Titel
    with col2:
        st.markdown(f"## {unit_title}")
    
    # Rechte Spalte: Aktions-Buttons
    with col3:
        btn_col1, btn_col2, btn_col3 = st.columns(3)
        
        # Umbenennen-Button
        with btn_col1:
            with st.popover("✏️", help="Lerneinheit umbenennen"):
                st.markdown("### Lerneinheit umbenennen")
                with st.form(f"rename_unit_{unit_id}"):
                    new_title = st.text_input("Neuer Titel", value=unit_title)
                    col_cancel, col_save = st.columns(2)
                    with col_cancel:
                        cancel = st.form_submit_button("Abbrechen", use_container_width=True)
                    with col_save:
                        save = st.form_submit_button("Speichern", type="primary", use_container_width=True)
                    
                    if save and new_title.strip() and new_title != unit_title:
                        success, error = update_learning_unit(unit_id, new_title.strip())
                        if success:
                            st.success("Lerneinheit umbenannt!")
                            st.rerun()
                        else:
                            st.error(error or "Fehler beim Umbenennen")
        
        # Löschen-Button
        with btn_col2:
            with st.popover("🗑️", help="Lerneinheit löschen"):
                st.markdown("### Lerneinheit löschen")
                st.warning(f"Möchten Sie die Lerneinheit **{unit_title}** wirklich löschen?")
                st.caption("Diese Aktion kann nicht rückgängig gemacht werden. Alle Abschnitte, Materialien und Aufgaben werden ebenfalls gelöscht.")
                
                col_cancel, col_delete = st.columns(2)
                with col_cancel:
                    st.button("Abbrechen", key="cancel_delete", use_container_width=True)
                with col_delete:
                    if st.button("Löschen", type="primary", key="confirm_delete", use_container_width=True):
                        success, error = delete_learning_unit(unit_id)
                        if success:
                            st.success("Lerneinheit gelöscht!")
                            # State zurücksetzen und zur Übersicht navigieren
                            state = UnitEditorState()
                            state.reset()
                            st.session_state.view = 'overview'
                            st.session_state.selected_unit_id = None
                            st.rerun()
                        else:
                            st.error(error or "Fehler beim Löschen")
        
        # Einstellungen-Button (Platzhalter für weitere Funktionen)
        with btn_col3:
            with st.popover("⚙️", help="Weitere Einstellungen"):
                st.markdown("### Einstellungen")
                st.info("Weitere Einstellungen werden in Kürze verfügbar sein.")
                # Hier könnten später weitere Optionen hinzugefügt werden:
                # - Export als PDF
                # - Duplizieren
                # - Versionshistorie
                # - Berechtigungen
    
    return False