# app/pages/6_Live_Unterricht.py
import streamlit as st

# Seitenkonfiguration


from streamlit import session_state as state
import time

# Importiere UI-Komponenten
from components.ui_components import render_sidebar_with_course_selection

# Importiere notwendige DB-Funktionen
from utils.db_queries import (
    get_sections_for_unit,
    get_section_statuses_for_unit_in_course,
    publish_section_for_course,
    unpublish_section_for_course,
    get_submission_status_matrix,
    get_task_details,
    get_submission_for_task,
    update_submission_teacher_override
)

# Hilfsfunktion für Aufgaben-Label
def get_task_label(task, max_length=50):
    """Erstellt ein Label für eine Aufgabe im Format '(order) [Erste Zeichen der Instruction]'"""
    # order_in_section ist 0-basiert in der DB, aber wir wollen 1-basiert anzeigen
    order = task.get('order_in_section', 0) + 1
    instruction = task.get('instruction', 'Keine Anweisung')
    # Kürze die Instruction wenn nötig
    if len(instruction) > max_length:
        instruction = instruction[:max_length] + "..."
    return f"({order}) {instruction}"

# --- Zugriffskontrolle ---
if 'role' not in state or state.role != 'teacher':
    st.error("Zugriff verweigert. Nur Lehrer können diese Seite sehen.")
    st.stop()

# --- Hauptbereich ---
if 'user' not in state or state.user is None:
    st.warning("Fehler: Kein Benutzer eingeloggt.")
    st.stop()
teacher_id = state.user.id

# Funktion für zusaetzlichen Sidebar-Content
def render_live_controls(selected_course, selected_unit):
    """Zeigt Live-Unterricht spezifische Kontrollen in der Sidebar."""
    st.subheader("⚙️ Optionen")
    
    # Auto-Refresh Toggle
    auto_refresh = st.toggle(
        "Auto-Refresh",
        value=False,
        help="Aktualisiert die Anzeige automatisch alle 5 Sekunden"
    )
    
    if auto_refresh:
        st.caption("🔄 Aktualisiert alle 5 Sekunden")
        # Placeholder für spätere Auto-Refresh Implementierung
    
    # Manueller Refresh Button
    if st.button("🔄 Jetzt aktualisieren", use_container_width=True):
        # Clear alle Caches vor Seitenneuladung
        from utils.cache_manager import CacheManager
        CacheManager.clear_all_caches()
        st.rerun()
    
    # Cache Debug Panel
    from utils.cache_manager import CacheManager
    CacheManager.render_debug_panel()

# --- Sidebar mit Kurs- und Einheitenauswahl ---
selected_course, selected_unit, _ = render_sidebar_with_course_selection(
    teacher_id,
    show_unit_selection=True,
    additional_content=render_live_controls if teacher_id else None
)

# --- Seitenkonfiguration und Titel ---
st.title("🚀 Live Unterricht Cockpit")
st.markdown("Wählen Sie einen Kurs und eine Lerneinheit, um den Freigabestatus der Abschnitte live zu steuern.")

# --- Abschnitt-Freigabe (nur wenn Kurs und Einheit gewählt) ---
if selected_course and selected_unit:
    st.subheader(f"Abschnitt-Freigabe für: '{selected_unit['title']}' in Kurs '{selected_course['name']}'")

    # 1. Abschnitte für die Einheit holen
    sections, error_sections = get_sections_for_unit(selected_unit['id'])
    if error_sections:
        st.error(f"Fehler beim Laden der Abschnitte: {error_sections}")
        sections = []
    elif sections is None: sections = []

    # 2. Status für diese Abschnitte im Kurs holen
    section_statuses, error_statuses = get_section_statuses_for_unit_in_course(selected_unit['id'], selected_course['id'])
    if error_statuses:
        st.error(f"Fehler beim Laden der Freigabestatus: {error_statuses}")
        # Weitermachen, aber ohne Status-Infos
        section_statuses = {}
    elif section_statuses is None: section_statuses = {}


    if not sections:
        st.info("Diese Lerneinheit enthält noch keine Abschnitte.")
    else:
        # Anzeige und Steuerung für jeden Abschnitt
        for section in sections:
            section_id = section['id']
            section_title = section.get('title', f"Abschnitt {section.get('order_in_unit', 0) + 1}")
            is_published = section_statuses.get(section_id, False) # Default auf False

            col1, col2 = st.columns([0.8, 0.2])

            with col1:
                st.markdown(f"**{section_title}** (ID: `{section_id}`)")

            with col2:
                # Der Toggle löst bei Änderung direkt die Aktion aus
                new_status = st.toggle(
                    "Veröffentlicht",
                    value=is_published,
                    key=f"toggle_{section_id}_{selected_course['id']}",
                    label_visibility="collapsed" # Nur den Toggle anzeigen
                )

                # Prüfe, ob sich der Status durch User-Interaktion geändert hat
                if new_status != is_published:
                    with st.spinner("Aktualisiere Status..."):
                        success = False
                        error_msg = None
                        if new_status: # Soll veröffentlicht werden
                            success, error_msg = publish_section_for_course(section_id, selected_course['id'])
                        else: # Soll zurückgezogen werden
                            success, error_msg = unpublish_section_for_course(section_id, selected_course['id'])

                        if success:
                            st.toast(f"Status für '{section_title}' aktualisiert!", icon="✅")
                            # Kurze Pause und Rerun, um den neuen Status korrekt anzuzeigen
                            # (Manchmal braucht der Toggle ein Rerun, um den neuen DB-Wert zu reflektieren)
                            time.sleep(0.5) # Kurze Pause reicht meist
                            st.rerun()
                        else:
                            st.toast(f"Fehler bei '{section_title}': {error_msg}", icon="❌")
                            # Hier kein Rerun, damit der Toggle auf den alten Wert zurückspringt

            st.divider()

# --- Live-Übersicht mit Matrix-Ansicht ---
if selected_course and selected_unit:
    st.subheader("📊 Live-Übersicht der Schüler-Abgaben")
    
    # Lade die Matrix-Daten
    with st.spinner("Lade Übersicht..."):
        matrix_data, error = get_submission_status_matrix(selected_course['id'], selected_unit['id'])
    
    if error:
        st.error(f"Fehler beim Laden der Übersicht: {error}")
    elif not matrix_data:
        st.warning("Keine Daten verfügbar.")
    else:
        # Debug-Info anzeigen falls vorhanden
        if 'debug_info' in matrix_data:
            with st.expander("🐛 Debug-Informationen"):
                st.json(matrix_data['debug_info'])
        # Debug: Zeige Struktur-Info
        if not matrix_data.get('sections'):
            debug_msg = f"Keine Sections gefunden. Matrix-Daten-Schlüssel: {list(matrix_data.keys())}"
            if isinstance(matrix_data, dict):
                debug_msg += f"\nStudenten: {len(matrix_data.get('students', []))}"
                debug_msg += f"\nTotal Tasks: {matrix_data.get('total_tasks', 0)}"
                # Versuche direkt die sections für diese Unit zu laden
                from utils.db_queries import get_sections_for_unit
                sections, err = get_sections_for_unit(selected_unit['id'])
                debug_msg += f"\nDirekte Section-Abfrage: {len(sections) if sections else 0} sections"
                if err:
                    debug_msg += f"\nSection-Fehler: {err}"
            st.warning(debug_msg)
        
        # Zeige Gesamtstatistiken
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Schüler im Kurs", len(matrix_data.get('students', [])))
        with col2:
            st.metric("Aufgaben gesamt", matrix_data.get('total_tasks', 0))
        with col3:
            progress = 0
            if matrix_data.get('total_tasks', 0) > 0:
                total_possible = len(matrix_data.get('students', [])) * matrix_data.get('total_tasks', 0)
                if total_possible > 0:
                    progress = matrix_data.get('total_submissions', 0) / total_possible
            st.metric("Gesamtfortschritt", f"{progress:.0%}")
        
        st.divider()
        
        # Tab-Ansicht für verschiedene Views
        tab1, tab2 = st.tabs(["👥 Schüler-Übersicht", "📝 Aufgaben-Übersicht"])
        
        with tab1:
            # Schüler-Matrix View
            if not matrix_data.get('students'):
                st.info("Keine Schüler in diesem Kurs.")
            else:
                # Zeige Schüler in Karten-Layout
                cols_per_row = 4
                students = matrix_data.get('students', [])
                
                for i in range(0, len(students), cols_per_row):
                    cols = st.columns(cols_per_row)
                    for j in range(cols_per_row):
                        if i + j < len(students):
                            student = students[i + j]
                            with cols[j]:
                                with st.container():
                                    # Schüler-Karte
                                    st.markdown(f"**👤 {student['display_name']}**")
                                    
                                    # Berechne Fortschritt für diesen Schüler
                                    total_tasks = 0
                                    completed_tasks = 0
                                    
                                    for section in matrix_data.get('sections', []):
                                        for task in section.get('tasks', []):
                                            total_tasks += 1
                                            submission = section['submissions'].get(student['student_id'], {}).get(task['id'], {})
                                            if submission.get('status') == 'submitted':
                                                completed_tasks += 1
                                    
                                    # Zeige Fortschritt
                                    if total_tasks > 0:
                                        progress = completed_tasks / total_tasks
                                        st.progress(progress)
                                        st.caption(f"{completed_tasks}/{total_tasks} erledigt")
                                    else:
                                        # Debug: Zeige warum keine Aufgaben
                                        section_count = len(matrix_data.get('sections', []))
                                        st.caption(f"Keine Aufgaben (Sections: {section_count})")
                                    
                                    # Expandable Details
                                    with st.expander("Details anzeigen"):
                                        for section in matrix_data.get('sections', []):
                                            if section.get('tasks'):
                                                st.markdown(f"**{section['title']}**")
                                                for task in section['tasks']:
                                                    submission = section['submissions'].get(student['student_id'], {}).get(task['id'], {})
                                                    status_icon = "✅" if submission.get('status') == 'submitted' else "⚪"
                                                    
                                                    col_icon, col_task = st.columns([1, 9])
                                                    with col_icon:
                                                        st.write(status_icon)
                                                    with col_task:
                                                        if submission.get('status') == 'submitted':
                                                            if st.button(get_task_label(task), key=f"view_{student['student_id']}_{task['id']}"):
                                                                # Speichere Auswahl im Session State für Detail-Ansicht
                                                                state.selected_submission = {
                                                                    'student_id': student['student_id'],
                                                                    'student_name': student['display_name'],
                                                                    'task_id': task['id'],
                                                                    'task_title': get_task_label(task),
                                                                    'section_title': section['title']
                                                                }
                                                        else:
                                                            st.write(get_task_label(task))
                                                st.divider()
        
        with tab2:
            # Aufgaben-Matrix View
            if not matrix_data.get('sections'):
                st.info("Keine Abschnitte mit Aufgaben verfügbar.")
            else:
                for section in matrix_data.get('sections', []):
                    if section.get('tasks'):
                        st.subheader(f"📁 {section['title']}")
                        
                        # Zeige Aufgaben als Karten
                        task_cols_per_row = 3
                        tasks = section.get('tasks', [])
                        
                        for i in range(0, len(tasks), task_cols_per_row):
                            cols = st.columns(task_cols_per_row)
                            for j in range(task_cols_per_row):
                                if i + j < len(tasks):
                                    task = tasks[i + j]
                                    with cols[j]:
                                        with st.container():
                                            st.info(f"📝 {get_task_label(task)}")
                                            
                                            # Berechne Abgabe-Statistik
                                            submissions_count = 0
                                            for student in matrix_data.get('students', []):
                                                submission = section['submissions'].get(student['student_id'], {}).get(task['id'], {})
                                                if submission.get('status') == 'submitted':
                                                    submissions_count += 1
                                            
                                            total_students = len(matrix_data.get('students', []))
                                            if total_students > 0:
                                                progress = submissions_count / total_students
                                                st.progress(progress)
                                                st.caption(f"{submissions_count}/{total_students} abgegeben")
                                            
                                            # Expander für Details
                                            with st.expander("Abgaben anzeigen"):
                                                for student in matrix_data.get('students', []):
                                                    submission = section['submissions'].get(student['student_id'], {}).get(task['id'], {})
                                                    if submission.get('status') == 'submitted':
                                                        col1, col2 = st.columns([4, 1])
                                                        with col1:
                                                            st.write(f"✅ {student['display_name']}")
                                                        with col2:
                                                            if st.button("Ansehen", key=f"view_task_{task['id']}_{student['student_id']}"):
                                                                state.selected_submission = {
                                                                    'student_id': student['student_id'],
                                                                    'student_name': student['display_name'],
                                                                    'task_id': task['id'],
                                                                    'task_title': get_task_label(task),
                                                                    'section_title': section['title']
                                                                }
                                                                st.rerun()
                                                    else:
                                                        st.write(f"⚪ {student['display_name']}")
                        
                        st.divider()

# --- Detail-Ansicht für ausgewählte Submission ---
if 'selected_submission' in state and state.selected_submission:
    st.divider()
    st.subheader("📋 Submission-Details")
    
    sel = state.selected_submission
    st.markdown(f"**Schüler:** {sel['student_name']} | **Aufgabe:** {sel['task_title']} | **Abschnitt:** {sel['section_title']}")
    
    # Lade die Details
    with st.spinner("Lade Details..."):
        # Hole Aufgaben-Details
        task_details, error = get_task_details(sel['task_id'])
        if error:
            st.error(f"Fehler beim Laden der Aufgabe: {error}")
            task_details = {}
        
        # Hole Submission
        submission, error = get_submission_for_task(sel['student_id'], sel['task_id'])
        if error:
            st.error(f"Fehler beim Laden der Einreichung: {error}")
            submission = {}
    
    # Zeige Details in zwei Spalten
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📋 Aufgabenstellung")
        if task_details and task_details.get('instruction'):
            st.write(task_details.get('instruction'))
            if task_details.get('feedback_focus') or task_details.get('assessment_criteria'):
                with st.expander("Bewertungskriterien"):
                    criteria = task_details.get('feedback_focus') or task_details.get('assessment_criteria', [])
                    if isinstance(criteria, list) and criteria:
                        for criterion in criteria:
                            st.write(f"• {criterion}")
                    elif criteria:
                        st.write(criteria)
        else:
            st.warning("Aufgabenstellung konnte nicht geladen werden.")
            if error:
                st.caption(f"Fehler: {error}")
    
    with col2:
        st.markdown("#### ✍️ Schülerlösung")
        if submission and submission.get('submission_data'):
            solution_text = submission['submission_data'].get('text', str(submission['submission_data']))
            st.text_area("", solution_text, height=200, disabled=True, key="submission_text_detail")
            
            # Zeige Zeitstempel
            if submission.get('submitted_at'):
                st.caption(f"Eingereicht am: {submission['submitted_at']}")
        else:
            st.write("Keine Einreichung gefunden.")
    
    # Feedback-Bearbeitungsbereich
    if submission:
        st.divider()
        st.markdown("#### 📝 Feedback & Bewertung")
        
        # Robuste Feedback-Extraktion mit Hierarchie
        # 1. Teacher Override (höchste Priorität)
        # 2. Strukturiertes Feedback (feed_back/feed_forward)  
        # 3. Mastery Insights (für Mastery-Tasks)
        # 4. Standard AI Feedback (Fallback)
        
        display_feedback = None
        feedback_source = None
        
        # Prüfe Teacher Override
        if submission.get('teacher_override_feedback'):
            display_feedback = submission['teacher_override_feedback']
            feedback_source = 'teacher'
        # Prüfe strukturiertes Feedback
        elif submission.get('feed_back_text') or submission.get('feed_forward_text'):
            feedback_source = 'structured'
        # Prüfe Mastery Insights
        elif submission.get('ai_insights'):
            try:
                insights = submission.get('ai_insights', {})
                if isinstance(insights, dict):
                    display_feedback = insights.get('feedback', insights.get('explanation'))
                    if display_feedback:
                        feedback_source = 'mastery'
                elif isinstance(insights, str):
                    # Falls ai_insights als String gespeichert wurde
                    try:
                        import json
                        insights_dict = json.loads(insights)
                        display_feedback = insights_dict.get('feedback', insights_dict.get('explanation'))
                        if display_feedback:
                            feedback_source = 'mastery'
                    except:
                        display_feedback = insights
                        feedback_source = 'mastery'
            except Exception as e:
                print(f"Error parsing ai_insights: {e}")
        # Fallback auf Standard AI Feedback
        elif submission.get('ai_feedback'):
            display_feedback = submission['ai_feedback']
            feedback_source = 'standard'
        
        if submission.get('feed_back_text') and submission.get('feed_forward_text') and not submission.get('teacher_override_feedback'):
            with st.expander("Vorschau des KI-Feedbacks", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**📍 Feed-Back (Wo steht der Schüler?):**")
                    st.info(submission['feed_back_text'])
                with col2:
                    st.markdown("**🎯 Feed-Forward (Nächste Schritte):**")
                    st.success(submission['feed_forward_text'])
        elif display_feedback and feedback_source == 'mastery' and not submission.get('teacher_override_feedback'):
            with st.expander("Vorschau des Mastery-Feedbacks", expanded=True):
                st.info(display_feedback)
        
        # Formular für Feedback-Bearbeitung
        with st.form(f"feedback_form_detail_{submission['id']}"):
            # Prüfe ob strukturiertes Feedback vorhanden ist
            has_structured_feedback = submission.get('feed_back_text') and submission.get('feed_forward_text')
            is_edited = bool(submission.get('teacher_override_feedback'))
            
            if is_edited:
                st.info("✏️ Sie haben das Feedback bereits bearbeitet.")
                # Bei bearbeitetem Feedback zeige es als einzelnes Feld
                teacher_feedback = st.text_area(
                    "Feedback für den Schüler:",
                    value=submission.get('teacher_override_feedback', ''),
                    height=200,
                    key="feedback_input_detail",
                    help="Ihr bearbeitetes Feedback"
                )
            elif has_structured_feedback:
                st.caption("🤖 KI-generiertes strukturiertes Feedback - Sie können beide Teile bearbeiten:")
                
                # Zwei getrennte Felder für Feed-Back und Feed-Forward
                feed_back_edit = st.text_area(
                    "📍 Feed-Back (Wo steht der Schüler?):",
                    value=submission.get('feed_back_text', ''),
                    height=100,
                    key="feed_back_input_detail",
                    help="Beschreibung des Ist-Zustands"
                )
                
                feed_forward_edit = st.text_area(
                    "🎯 Feed-Forward (Nächste Schritte):",
                    value=submission.get('feed_forward_text', ''),
                    height=100,
                    key="feed_forward_input_detail",
                    help="Konkrete Verbesserungsvorschläge"
                )
                
                # Kombiniere für Speicherung
                teacher_feedback = f"{feed_back_edit}\n\n{feed_forward_edit}"
            else:
                # Fallback: Nutze die ermittelte Feedback-Hierarchie
                if display_feedback:
                    if feedback_source == 'mastery':
                        st.caption("🤖 Mastery-Feedback - Sie können es direkt bearbeiten:")
                    elif feedback_source == 'structured':
                        st.caption("🤖 Strukturiertes Feedback - Sie können es direkt bearbeiten:")
                    else:
                        st.caption("🤖 KI-generiertes Feedback - Sie können es direkt bearbeiten:")
                    default_feedback = display_feedback
                else:
                    st.caption("💬 Neues Feedback erstellen:")
                    default_feedback = ''
                
                teacher_feedback = st.text_area(
                    "Feedback für den Schüler:",
                    value=default_feedback,
                    height=150,
                    key="feedback_input_detail",
                    help="Bearbeiten Sie das KI-Feedback oder schreiben Sie eigenes Feedback"
                )
            
            # Note-Eingabe
            col1, col2 = st.columns([1, 3])
            with col1:
                current_grade = submission.get('teacher_override_grade') or submission.get('ai_grade', '')
                teacher_grade = st.text_input(
                    "Note:",
                    value=current_grade,
                    placeholder="z.B. 1+, gut",
                    key="grade_input_detail"
                )
            
            # Submit-Buttons
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                save_button = st.form_submit_button("💾 Speichern", type="primary")
            with col2:
                if is_edited:
                    reset_button = st.form_submit_button("🔄 KI-Feedback wiederherstellen")
                else:
                    reset_button = False
            with col3:
                close_button = st.form_submit_button("❌ Schließen")
            
            if save_button:
                # Speichere nur wenn sich etwas geändert hat
                feedback_changed = teacher_feedback != submission.get('ai_feedback', '')
                grade_changed = teacher_grade != submission.get('ai_grade', '')
                
                if feedback_changed or grade_changed:
                    success, error = update_submission_teacher_override(
                        submission['id'],
                        teacher_feedback if feedback_changed else None,
                        teacher_grade if grade_changed else None
                    )
                    
                    if success:
                        st.success("✅ Feedback gespeichert!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ Fehler: {error}")
                else:
                    st.info("Keine Änderungen zu speichern.")
            
            elif reset_button:
                # Setze auf KI-Feedback zurück
                success, error = update_submission_teacher_override(
                    submission['id'],
                    None,  # Lösche teacher_override_feedback
                    None   # Lösche teacher_override_grade
                )
                if success:
                    st.info("↩️ KI-Feedback wiederhergestellt")
                    time.sleep(1)
                    st.rerun()
            
            elif close_button:
                del state.selected_submission
                st.rerun()