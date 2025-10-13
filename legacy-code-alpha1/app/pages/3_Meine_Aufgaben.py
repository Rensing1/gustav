# app/pages/3_Meine_Aufgaben.py
import streamlit as st
from streamlit import session_state as state

# Seitenkonfiguration

import time
from datetime import datetime

# Importiere UI-Komponenten
from components.ui_components import render_sidebar_with_course_selection
from components.submission_input import render_submission_input, handle_file_submission

# Importiere notwendige DB-Funktionen
from utils.db_queries import (
    get_published_section_details_for_student,
    create_submission,
    get_submission_by_id,
    get_submission_history,
    get_remaining_attempts
)

from utils.session_client import get_user_supabase_client
import requests
# from ai.feedback import generate_ai_insights_for_submission  # Nicht mehr benötigt - Worker übernimmt

# --- Zugriffskontrolle ---
if 'role' not in state or state.role != 'student':
    st.error("Zugriff verweigert. Nur Schüler können ihre Aufgaben sehen.")
    st.stop()

# --- Hauptbereich ---
if 'user' not in state or state.user is None:
    st.warning("Fehler: Kein Benutzer eingeloggt.")
    st.stop()
student_id = state.user.id

# --- Sidebar mit Kurs- und Einheitenauswahl ---
selected_course, selected_unit, _ = render_sidebar_with_course_selection(
    student_id,
    show_unit_selection=True
)

# --- Seitenkonfiguration und Titel ---
st.title("📝 Meine Aufgaben")
st.markdown("Hier siehst du die Aufgaben deiner Kurse und kannst Lösungen einreichen.")

# --- Abschnitte, Materialien und Aufgaben anzeigen ---
if selected_course and selected_unit:
    st.header(f"Lerneinheit: {selected_unit['title']}")
    st.caption(f"Kurs: {selected_course['name']}")

    section_details, error_details = get_published_section_details_for_student(
        selected_unit['id'], selected_course['id'], student_id
    )

    if error_details:
        st.error(f"Fehler beim Laden der Lerninhalte: {error_details}")
    elif not section_details:
        st.info("Für diese Lerneinheit wurden in diesem Kurs noch keine Abschnitte veröffentlicht.")
    else:
        # Globaler Aufgabenzähler über alle Sections
        global_task_counter = 1
        
        for section in section_details:
            st.subheader(f"Abschnitt {section.get('order_in_unit', 0) + 1}: {section.get('title', 'Unbenannt')}")

            # --- Materialien anzeigen ---
            if materials := section.get('materials', []):
                st.markdown("**Materialien:**")
                for material in materials:
                    mat_title = material.get('title', 'Material')
                    mat_type = material.get('type', 'unbekannt')
                    
                    icon = {"link": "🔗", "file": "📁", "markdown": "📝", "applet": "</>"}.get(mat_type, "📄")
                    expander_title = f"{icon} Material: {mat_title}"

                    with st.expander(expander_title, expanded=True):
                        if mat_type == 'markdown':
                            st.markdown(material.get('content', ''), unsafe_allow_html=False)
                        
                        elif mat_type == 'link':
                            if url := material.get('content'):
                                st.link_button(f"Link öffnen", url, help=url)
                            else:
                                st.warning("Link-URL nicht gefunden oder ungültig.")

                        elif mat_type == 'file':
                            if file_path := material.get('path'):
                                # Nutze Session-Client für Storage-Zugriff
                                from utils.session_client import get_user_supabase_client
                                supabase = get_user_supabase_client()
                                try:
                                    signed_url = supabase.storage.from_("section_materials").create_signed_url(file_path, 60)['signedURL']
                                    
                                    response = requests.get(signed_url)
                                    response.raise_for_status()
                                    file_data = response.content

                                    mime_type = material.get('mime_type', '')
                                    if 'image' in mime_type:
                                        # Use 3 columns to center the image and control its width
                                        _col1, col_img, _col2 = st.columns([1, 4, 1])
                                        with col_img:
                                            st.image(file_data, caption=material.get('filename'), use_container_width=True)
                                    else:
                                        st.download_button(
                                            label=f"📥 {material.get('filename')} herunterladen",
                                            data=file_data,
                                            file_name=material.get('filename'),
                                            mime=mime_type
                                        )
                                except Exception as e:
                                    st.error(f"Fehler beim Laden der Datei: {e}")
                            else:
                                st.warning("Für dieses Material wurde keine Datei gefunden.")
                        
                        elif mat_type == 'applet':
                            applet_code = material.get('content', '')
                            if applet_code:
                                st.components.v1.html(applet_code, height=600, scrolling=True)
                            else:
                                st.warning("Für dieses Applet wurde kein Code gefunden.")

                        else:
                            st.warning(f"Unbekannter oder veralteter Materialtyp: {mat_type}")
                            st.json(material)

                st.write("") # Spacer


            # --- Aufgaben anzeigen ---
            if tasks := section.get('tasks', []):
                st.markdown("**Aufgaben:**")
                for task in tasks:
                    task_id = task['id']
                    st.markdown(f"#### Aufgabe {global_task_counter}")
                    st.markdown(task.get('instruction', 'Keine Anweisung.'))
                    global_task_counter += 1  # Erhöhe den globalen Zähler

                    history, error_history = get_submission_history(student_id, task_id)
                    remaining, max_attempts, error_remaining = get_remaining_attempts(student_id, task_id)
                    if max_attempts is None:
                        max_attempts = task.get('max_attempts', 1)

                    if error_history or error_remaining:
                        st.error("Fehler beim Laden der Abgabe-Informationen.")
                    else:
                        if history:
                            st.markdown("**Bisherige Abgaben:**")
                            for sub in reversed(history):
                                attempt_num = sub.get('attempt_number', '?')
                                created_at = sub.get('created_at', '')
                                if not created_at:
                                    created_at_fmt = 'Datum unbekannt'
                                else:
                                    try:
                                        # Korrigiere Mikrosekunden auf genau 6 Stellen für Python
                                        created_at_clean = created_at.replace('Z', '+00:00')
                                        if '.' in created_at_clean and '+' in created_at_clean:
                                            parts = created_at_clean.split('.')
                                            if len(parts) == 2:
                                                microsec_part = parts[1].split('+')[0][:6].ljust(6, '0')  # Genau 6 Stellen
                                                timezone_part = '+' + parts[1].split('+')[1]
                                                created_at_clean = f"{parts[0]}.{microsec_part}{timezone_part}"
                                        dt_obj = datetime.fromisoformat(created_at_clean)
                                        created_at_fmt = dt_obj.strftime('%d.%m.%Y, %H:%M Uhr')
                                    except (ValueError, AttributeError):
                                        created_at_fmt = 'Ungültiges Datum'

                                with st.expander(f"Versuch {attempt_num} (eingereicht am {created_at_fmt})", expanded=(attempt_num == len(history))):
                                    
                                    # Zeige Text-Submission
                                    if sol_data := sub.get('submission_data'):
                                        st.text_area("Deine Antwort:", value=sol_data.get('text',''), disabled=True, key=f"sol_{sub['id']}")
                                    
                                    # Feedback Bereich (KI und/oder Lehrer)
                                    submission_obj = sub # Das Submission-Objekt aus der History-Schleife
                                    if submission_obj:
                                        # Container für das Feedback - wird dynamisch aktualisiert
                                        feedback_container = st.empty()
                                        
                                        # Prüfe ob Feedback vorhanden ist
                                        has_teacher_feedback = submission_obj.get('teacher_override_feedback') or submission_obj.get('teacher_override_grade')
                                        has_structured_feedback = submission_obj.get('feed_back_text') and submission_obj.get('feed_forward_text')
                                        has_ai_feedback = submission_obj.get('ai_feedback')
                                        
                                        # Initial Check: Hat die Submission bereits abgeschlossenes Feedback?
                                        feedback_status = submission_obj.get('feedback_status', 'pending')
                                        if feedback_status == 'completed' and (has_teacher_feedback or has_structured_feedback or has_ai_feedback):
                                            # Feedback vorhanden - zeige es an
                                            with feedback_container.container():
                                                # Wenn Lehrer-Override vorhanden, zeige das bearbeitete Feedback
                                                if has_teacher_feedback:
                                                    with st.expander(" Feedback", expanded=True):
                                                        # Zeige das Feedback (entweder bearbeitet oder original)
                                                        feedback_text = submission_obj.get('teacher_override_feedback') or submission_obj.get('ai_feedback', '')
                                                        st.success(feedback_text)
                                                        
                                                        # Hinweis dass es bearbeitet wurde
                                                        st.caption("✏️ Dieses Feedback wurde von deinem Lehrer angepasst.")
                                                        
                                                        # Note wenn vorhanden
                                                        if submission_obj.get('teacher_override_grade'):
                                                            st.metric("Note", submission_obj['teacher_override_grade'])
                                                        elif submission_obj.get('ai_grade'):
                                                            st.metric("Vorläufige Bewertung", submission_obj['ai_grade'])
                                                
                                                # Strukturiertes KI-Feedback (neue Implementierung)
                                                elif has_structured_feedback:
                                                    with st.expander(" Feedback", expanded=True):
                                                        # Feed-Back: Wo stehe ich?
                                                        st.markdown("###  Wo du stehst:")
                                                        with st.container(border=True):
                                                            st.success(submission_obj['feed_back_text'])
                                                        
                                                        # Feed-Forward: Nächste Schritte
                                                        st.markdown("###  Dein nächster Schritt:")
                                                        with st.container(border=True):
                                                            st.info(submission_obj['feed_forward_text'])
                                                        
                                                        st.caption(" Automatisch generiertes Feedback")
                                                        
                                                        if submission_obj.get('ai_grade'):
                                                            st.metric("Vorläufige Bewertung", submission_obj['ai_grade'])
                                                
                                                # Fallback: Altes KI-Feedback Format
                                                elif has_ai_feedback:
                                                    with st.expander(" Feedback", expanded=True):
                                                        st.info(submission_obj['ai_feedback'])
                                                        st.caption(" Automatisch generiertes Feedback")
                                                        
                                                        if submission_obj.get('ai_grade'):
                                                            st.metric("Vorläufige Bewertung", submission_obj['ai_grade'])
                                        else:
                                            # Noch kein Feedback - zeige einfachen Wartestatus mit Auto-Refresh
                                            submission_id = submission_obj.get('id')
                                            if submission_id:
                                                
                                                # Zeige dauerhaften Wartestatus
                                                with feedback_container.container():
                                                    with st.expander("🤖 KI-Feedback", expanded=True):
                                                        if feedback_status == 'completed':
                                                            # Feedback ist fertig - zeige Toast und lade neu
                                                            st.toast("✅ Feedback ist bereit!", icon="🎉")
                                                            time.sleep(1)
                                                            st.rerun()
                                                        elif feedback_status == 'failed':
                                                            st.error("❌ Feedback-Generierung fehlgeschlagen. Bitte wende dich an deinen Lehrer.")
                                                        else:
                                                            # Zeige Wartestatus (ohne Polling)
                                                            if feedback_status == 'processing':
                                                                st.info("⚙️ **Feedback wird generiert...**")
                                                            elif feedback_status == 'retry':
                                                                retry_count = submission_obj.get('retry_count', 0)
                                                                st.warning(f"🔄 Erneuter Versuch ({retry_count}/3)")
                                                            else:
                                                                st.info("🔄 **Abgabe wird ausgewertet...**")
                                                            
                                                            # Manueller Refresh-Button
                                                            if st.button("🔄 Status prüfen", key=f"check_{submission_id}"):
                                                                st.rerun()

                        if remaining is not None and remaining > 0:
                            st.info(f"Du hast noch {remaining} von {max_attempts} Versuchen übrig.")
                            
                            # Prüfe ob bereits eine aktuelle Submission existiert
                            recent_submissions = []
                            if history:  # history wurde oben bereits geladen
                                # Prüfe die letzte Submission - ist sie sehr recent (letzten 5 Minuten)?
                                last_submission = history[-1] if history else None
                                if last_submission:
                                    from datetime import datetime, timezone, timedelta
                                    submission_time_str = last_submission.get('created_at', '')
                                    try:
                                        # Parse Timestamp
                                        submission_time_clean = submission_time_str.replace('Z', '+00:00')
                                        if '.' in submission_time_clean and '+' in submission_time_clean:
                                            parts = submission_time_clean.split('.')
                                            if len(parts) == 2:
                                                microsec_part = parts[1].split('+')[0][:6].ljust(6, '0')
                                                timezone_part = '+' + parts[1].split('+')[1]
                                                submission_time_clean = f"{parts[0]}.{microsec_part}{timezone_part}"
                                        
                                        submission_time = datetime.fromisoformat(submission_time_clean)
                                        time_diff = datetime.now(timezone.utc) - submission_time
                                        
                                        # Wenn die letzte Submission weniger als 10 Sekunden alt ist, zeige sie statt Form
                                        if time_diff.total_seconds() < 10:  # 10 Sekunden
                                            recent_submissions = [last_submission]
                                    except:
                                        # Bei Parsing-Fehlern einfach weiter mit Form
                                        pass
                            
                            if recent_submissions:
                                # Zeige die aktuelle Submission statt Input-Form
                                recent_sub = recent_submissions[0]
                                submission_id = recent_sub.get('id')
                                submission_text = recent_sub.get('submission_data', {}).get('text', '')
                                
                                st.markdown("**Deine eingereichte Antwort:**")
                                st.info(submission_text)
                                
                                # Zeige Feedback-Status
                                feedback_status = recent_sub.get('feedback_status', 'pending')
                                if feedback_status == 'completed':
                                    st.toast("✅ Feedback ist bereit!", icon="🎉")
                                    st.success("🎉 **Dein Feedback ist da!**")
                                    if st.button("🔄 Seite neu laden", key=f"reload_{submission_id}"):
                                        st.rerun()
                                elif feedback_status == 'failed':
                                    st.error("❌ Feedback-Generierung fehlgeschlagen. Bitte wende dich an deinen Lehrer.")
                                else:
                                    # Zeige schlanken Wartestatus
                                    if feedback_status == 'processing':
                                        st.info("⚙️ **Feedback wird generiert...**")
                                    else:
                                        st.info("🔄 **Abgabe wird ausgewertet...**")
                                        
                            else:
                                # Keine aktuelle Submission - zeige Input-Form
                                submission_result = render_submission_input(task, student_id)
                                
                                if submission_result:
                                    if submission_result["type"] == "text":
                                        # Text-Submission verarbeiten
                                        solution_text = submission_result["content"]
                                        
                                        with st.spinner("Speichere deine Antwort..."):
                                            created_submission_obj, error_submit = create_submission(
                                                student_id, task_id, solution_text
                                            )

                                        if error_submit:
                                            st.error(f"Fehler beim Speichern: {error_submit}")
                                        elif created_submission_obj:
                                            # Erfolgreich gespeichert - trigger rerun
                                            st.success("✅ Antwort gespeichert!")
                                            time.sleep(0.5)
                                            st.rerun()
                                    
                                    elif submission_result["type"] == "file_upload":
                                        # File-Upload verarbeiten
                                        with st.spinner("Lade Datei hoch..."):
                                            success = handle_file_submission(submission_result)
                                        
                                        if success:
                                            time.sleep(2)
                                            st.rerun()
                                

                    st.divider()

            st.divider()

else:
    if not selected_course:
         st.info("ℹ️ Bitte wähle in der Sidebar einen Kurs aus.")
    elif not selected_unit:
         st.info("ℹ️ Bitte wähle in der Sidebar eine Lerneinheit aus.")
