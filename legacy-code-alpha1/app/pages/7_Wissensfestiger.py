# app/pages/7_Wissensfestiger.py
"""
Wissensfestiger-Modul für nachhaltiges Lernen mit Spaced Repetition
"""

import streamlit as st
from streamlit import session_state as state
from utils.db_queries import (
    get_next_due_mastery_task,
    get_next_mastery_task_or_unviewed_feedback,
    create_submission,
    get_mastery_stats_for_student,
    get_user_course_ids
)
# Queue-basierte Verarbeitung für Mastery-Tasks
from utils.mastery_state import MasterySessionState
from mastery.mastery_config import get_learning_level_label, get_learning_level_color
from components.ui_components import render_sidebar_with_course_selection
from components.mastery_progress import render_mastery_progress_card

# --- Zugriffskontrolle ---
if 'role' not in state or state.role != 'student':
    st.error("Zugriff verweigert. Diese Seite ist nur für Schüler zugänglich.")
    st.stop()

if 'user' not in state or state.user is None:
    st.warning("Fehler: Kein Benutzer eingeloggt.")
    st.stop()

student_id = state.user.id

# --- Helferfunktionen ---
def render_mastery_stats(selected_course, selected_unit):
    """Zeigt Wissensfestiger-Statistiken in der Sidebar."""
    if selected_course:
        render_mastery_progress_card(student_id, selected_course['id'])

# --- UI Implementierung ---
st.title("🎯 Wissensfestiger")
st.markdown("**Festige dein Wissen nachhaltig mit intelligentem Wiederholen!**")

# Sidebar
selected_course, _, _ = render_sidebar_with_course_selection(
    student_id,
    show_unit_selection=False,
    additional_content=render_mastery_stats
)

# Hauptbereich
if not selected_course:
    st.info("👈 Bitte wähle einen Kurs in der Seitenleiste aus.")
    st.stop()

selected_course_id = selected_course['id']

# Legacy-Migration für bestehende Sessions
MasterySessionState.migrate_legacy_session_state(selected_course_id)

# Kurswechsel-Detection: Bereinige State wenn Kurs gewechselt wurde
if 'last_mastery_course_id' not in st.session_state:
    st.session_state.last_mastery_course_id = selected_course_id
elif st.session_state.last_mastery_course_id != selected_course_id:
    # Kurswechsel erkannt - aktualisiere Tracking
    st.session_state.last_mastery_course_id = selected_course_id

# Kurs-spezifischen State abrufen
course_state = MasterySessionState.get_course_state(selected_course_id)


# Memory-Management: Alte Kurs-States bereinigen (bei mehr als 5 Kursen)
if len(st.session_state.get('mastery_course_state', {})) > 5:
    try:
        user_courses = get_user_course_ids(student_id)
        MasterySessionState.cleanup_old_courses(user_courses, max_age_hours=24)
    except Exception:
        # Bei Fehler: Sanftes Fallback ohne Cleanup
        pass

# Debug: Aktueller State
print(f"🔍 State Check - answer_submitted: {course_state['answer_submitted']}, current_task: {course_state['current_task'] is not None}")
if course_state['current_task']:
    print(f"   Current task ID: {course_state['current_task'].get('id', 'Unknown')}")
    print(f"   Current task instruction: {course_state['current_task'].get('instruction', 'Unknown')[:50]}...")

# Prüfe ob die aktuelle Task noch gültig ist (falls vorhanden)
current_task = course_state.get('current_task')
if current_task and not course_state.get('answer_submitted', False):
    # Immer neue Task laden wenn keine Antwort submitted ist
    # Das stellt sicher, dass wir immer die aktuellste fällige Aufgabe zeigen
    print(f"🔄 Clearing current task to load fresh due task")
    MasterySessionState.clear_task(selected_course_id, keep_feedback_context=False)
    current_task = None
    course_state = MasterySessionState.get_course_state(selected_course_id)

# Lade nächste Aufgabe - Prüfung verbessert für Robustheit
if not course_state.get('answer_submitted', False) and course_state.get('current_task') is None:
    print(f"📋 Lade nächste Task für student_id: {student_id}, course_id: {selected_course_id}")
    task_data = get_next_mastery_task_or_unviewed_feedback(student_id, selected_course_id)
    print(f"📨 Task-Data erhalten: type={task_data.get('type')}, has_task={task_data.get('task') is not None}")
    if task_data.get('task'):
        print(f"   New task ID: {task_data['task'].get('id', 'Unknown')}")
        print(f"   New task instruction: {task_data['task'].get('instruction', 'Unknown')[:50]}...")
    
    if task_data['type'] == 'show_feedback':
        # User hat ungelesenes Feedback - zeige diese Aufgabe statt neue
        task_id = task_data['task']['id']
        if not MasterySessionState.is_task_active_in_other_course(task_id, selected_course_id):
            # Die neue RPC-Funktion gibt bereits alle benötigten Daten zurück
            # Keine weiteren DB-Abfragen erforderlich
            MasterySessionState.set_task(
                selected_course_id, 
                task_data['task'], 
                task_data['submission']['id']
            )
        else:
            st.info("⏳ Eine Aufgabe wird gerade in einem anderen Kurs bearbeitet. Bitte warte einen Moment.")
            st.stop()
    elif task_data['type'] == 'new_task':
        if task_data['error']:
            if "Keine Aufgaben fällig" in task_data['error']:
                st.success("🎉 **Großartig!** Du hast alle fälligen Aufgaben bearbeitet!")
                st.balloons()
                st.info("Komm morgen wieder, um dein Wissen weiter zu festigen.")
            else:
                st.error(f"Fehler: {task_data['error']}")
            st.stop()
        
        task_id = task_data['task']['id'] 
        if not MasterySessionState.is_task_active_in_other_course(task_id, selected_course_id):
            MasterySessionState.set_task(selected_course_id, task_data['task'])
        else:
            st.info("⏳ Eine Aufgabe wird gerade in einem anderen Kurs bearbeitet. Bitte warte einen Moment.")
            st.stop()
    else:  # error
        st.error(f"Fehler: {task_data.get('error', 'Unbekannter Fehler')}")
        st.stop()

# Zeige aktuelle Aufgabe
if course_state['current_task']:
    task = course_state['current_task']
    st.markdown("---")

    # Fortschrittsanzeige
    mastery_progress = task.get('mastery_progress')
    # Debug logging
    print(f"DEBUG: task mastery_progress = {mastery_progress}, type = {type(mastery_progress)}")
    
    if mastery_progress is not None and isinstance(mastery_progress, dict) and mastery_progress.get('stability') is not None:
        stability = mastery_progress.get('stability', 0)
        st.caption(f"Aktuelle Stabilität: {stability:.1f} Tage")
    else:
        # Prüfe ob es wirklich eine neue Aufgabe ist indem wir nach vergangenen Submissions schauen
        from utils.db_queries import get_submission_history
        history, _ = get_submission_history(student_id, task['id'])
        if history and len(history) > 0:
            st.caption(f"🔄 **Wiederholung** - Du hast diese Aufgabe schon {len(history)}x bearbeitet")
        else:
            st.caption("🆕 **Neue Aufgabe** - Deine erste Begegnung mit diesem Konzept!")

    # Aufgabenstellung
    st.markdown("### 📝 Aufgabe")
    with st.container(border=True):
        st.markdown(task.get('instruction', 'Keine Aufgabenstellung verfügbar'))

    # Antwortbereich
    if not course_state['answer_submitted']:
        st.info("💡 **Tipp:** Bleibe auf dieser Seite, bis du dein Feedback gelesen und auf 'Nächste Aufgabe' geklickt hast.")
        with st.form("mastery_answer_form"):
            answer = st.text_area("✍️ Deine Antwort", height=200, placeholder="Erkläre in deinen eigenen Worten...")
            submit = st.form_submit_button("Antwort einreichen", type="primary", use_container_width=True)
            
            if submit:
                if not answer or not answer.strip():
                    st.error("Bitte gib eine Antwort ein.")
                else:
                    # Für Mastery-Tasks: Nutze die Queue für bessere Skalierbarkeit
                    # Der Worker wird die AI aufrufen und den Progress aktualisieren
                    
                    with st.spinner("Speichere deine Antwort..."):
                        submission_data = {
                            "text": answer.strip(),
                            "is_mastery": True  # Flag für den Worker
                        }
                        created_submission, error = create_submission(
                            student_id=student_id, 
                            task_id=task['id'], 
                            submission_data=submission_data
                        )
                    
                    if error:
                        st.error(f"Fehler beim Speichern: {error}")
                    else:
                        st.success("✅ Deine Antwort wurde zur Auswertung eingereicht. Das Ergebnis erscheint in Kürze.")
                        
                        # Extract submission_id from created_submission
                        if isinstance(created_submission, dict):
                            submission_id = created_submission.get('id')
                        else:
                            submission_id = str(created_submission) if created_submission else None
                        
                        print(f"DEBUG: created_submission = {created_submission}")
                        print(f"DEBUG: extracted submission_id = {submission_id}")
                        
                        if submission_id:
                            MasterySessionState.mark_submitted(
                                selected_course_id, 
                                answer.strip(), 
                                submission_id
                            )
                            st.rerun()
                        else:
                            st.error("Fehler: Keine Submission-ID erhalten")

    # Ergebnis anzeigen oder Queue-Status
    if course_state['answer_submitted']:
        submission_id = course_state.get('submission_id')
        if submission_id:
            # Lade Submission-Status aus DB
            from utils.db_queries import get_submission_by_id
            
            submission, error = get_submission_by_id(submission_id)
            if submission:
                feedback_status = submission.get('feedback_status', 'pending')
                
                if feedback_status == 'completed':
                    # Auto-Markierung: Feedback sofort als gelesen markieren
                    if submission.get('feedback_viewed_at') is None:
                        from utils.db_queries import mark_feedback_as_viewed_safe
                        auto_mark_success, auto_mark_error = mark_feedback_as_viewed_safe(submission_id)
                        if auto_mark_success:
                            print(f"✅ Feedback automatisch als gelesen markiert für submission_id: {submission_id}")
                        else:
                            print(f"⚠️ Fehler beim Auto-Markieren: {auto_mark_error}")
                    
                    # Zeige Ergebnisse
                    ai_insights = submission.get('ai_insights', {})
                    # Handle case where ai_insights might be a string (JSON)
                    if isinstance(ai_insights, str):
                        try:
                            import json
                            ai_insights = json.loads(ai_insights)
                        except:
                            ai_insights = {}
                    
                    if ai_insights:
                        # Wichtiger Hinweis für Benutzer
                        st.warning("⚠️ **Wichtig:** Bitte verlasse diese Seite nicht, während du dein Feedback liest. Klicke auf 'Nächste Aufgabe', wenn du fertig bist.")
                        
                        st.markdown("### 🎯 Deine Rückmeldung")
                        
                        # Mastery Score anzeigen
                        mastery_score = ai_insights.get('mastery_score', 0.0) if isinstance(ai_insights, dict) else 0.0
                        simulated_score = int(mastery_score * 4) + 1
                        level_label = {
                            1: "🤔 Das war noch nicht ganz richtig",
                            2: "💡 Ansatzweise korrekt", 
                            3: "✅ Gut gemacht!",
                            4: "👍 Sehr gut!",
                            5: "🌟 Exzellent!"
                        }.get(simulated_score, "Bewertung")
                        
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**Bewertung:** {level_label}")
                        with col2:
                            st.metric("Korrektheit", f"{mastery_score:.0%}")

                        # Eigene Antwort anzeigen
                        if course_state['last_answer']:
                            with st.expander("🔍 Deine eingereichte Antwort"):
                                st.markdown(course_state['last_answer'])

                        # KI-Feedback
                        st.markdown("### 💬 Dein persönliches Feedback")
                        feedback_text = submission.get('ai_feedback', 'Kein Feedback verfügbar.')
                        
                        # Feed-Back/Forward falls strukturiert vorhanden
                        if submission.get('feed_back_text') and submission.get('feed_forward_text'):
                            st.markdown("#### 🔍 Wo stehe ich?")
                            with st.container(border=True):
                                st.markdown(submission.get('feed_back_text', ''))

                            st.markdown("#### 🚀 Wie geht es weiter?")
                            with st.container(border=True):
                                st.markdown(submission.get('feed_forward_text', ''))
                        else:
                            # Fallback: Normales Feedback
                            with st.container(border=True):
                                st.markdown(feedback_text)

                        # Nächste Aufgabe Button
                        st.markdown("---")
                        if st.button("Nächste Aufgabe →", type="primary", use_container_width=True):
                            print(f"🔥 BUTTON CLICKED! Clearing state for course {selected_course_id}")
                            # Feedback wurde bereits auto-markiert, nur noch Session State bereinigen
                            success = MasterySessionState.clear_task_atomic(selected_course_id, submission_id)
                            print(f"   Clear task result: {success}")
                            
                            # Fallback: Falls atomic clear fehlschlägt, manuell clearen
                            if not success:
                                print(f"⚠️ Atomic clear failed, forcing manual clear")
                                state = MasterySessionState.get_course_state(selected_course_id)
                                state['current_task'] = None
                                state['answer_submitted'] = False
                                state['submission_id'] = None
                                state['last_answer'] = None
                            
                            # Debug: State nach Clear
                            debug_state = MasterySessionState.get_course_state(selected_course_id)
                            print(f"   State after clear: current_task={debug_state.get('current_task') is not None}, answer_submitted={debug_state.get('answer_submitted')}")
                            
                            st.rerun()
                    else:
                        st.warning("Feedback wurde verarbeitet, aber keine Daten verfügbar.")
                        
                elif feedback_status in ['pending', 'processing', 'retry']:
                    # Zeige Queue-Status wie in normalen Aufgaben
                    from utils.db_queries import get_submission_queue_position
                    
                    st.markdown("### ⏳ Auswertung läuft")
                    
                    queue_position = None
                    if feedback_status in ['pending', 'retry']:
                        try:
                            position, error = get_submission_queue_position(submission_id)
                            if not error and position is not None:
                                queue_position = position
                        except:
                            pass
                    
                    # Status-spezifische Nachricht
                    if feedback_status == 'pending':
                        st.info(f"⏳ In Warteschlange{f' (Position {queue_position})' if queue_position else ''}")
                    elif feedback_status == 'processing':
                        st.info("⚙️ Antwort wird gerade ausgewertet...")
                    elif feedback_status == 'retry':
                        retry_count = submission.get('retry_count', 0)
                        st.warning(f"🔄 Erneuter Versuch ({retry_count}/3){f' - Position {queue_position}' if queue_position else ''}")
                    
                    if queue_position and queue_position > 1:
                        estimated_wait = queue_position * 30  # 30 Sekunden pro Aufgabe
                        st.caption(f"Geschätzte Wartezeit: {estimated_wait // 60} Min. {estimated_wait % 60} Sek.")
                    
                    # Auto-Refresh
                    import time
                    time.sleep(5)
                    st.rerun()
                    
                elif feedback_status == 'failed':
                    st.error("❌ Auswertung fehlgeschlagen. Bitte versuche es erneut oder wende dich an deinen Lehrer.")
                    if st.button("Nochmal versuchen"):
                        # Reset f\u00fcr neuen Versuch
                        MasterySessionState.clear_task(selected_course_id, keep_feedback_context=False)
                        st.rerun()
            else:
                st.error(f"Fehler beim Laden der Einreichung: {error}")
        

# Hilfe-Expander
with st.expander("ℹ️ **Wie funktioniert der Wissensfestiger?**"):
    st.markdown("""
    ### Das Prinzip
    Der Wissensfestiger nutzt einen intelligenten Algorithmus, um dein Wissen nachhaltig zu festigen:
    
    - **Stabilität:** Jede Aufgabe hat eine "Stabilität", die angibt, wie gut die Information in deinem Gedächtnis verankert ist.
    - **Schwierigkeit:** Der Algorithmus lernt, wie schwierig eine Aufgabe für dich persönlich ist.
    - **Intelligente Wiederholung:** Basierend auf deiner Antwort werden Stabilität und Schwierigkeit angepasst und das nächste optimale Wiederholungsdatum berechnet.
    
    ### Tipps für effektives Lernen
    1. **Regelmäßigkeit:** Komm täglich für 10-15 Minuten vorbei.
    2. **Eigene Worte:** Erkläre Konzepte in deiner eigenen Sprache.
    3. **Keine Angst vor Fehlern:** Jeder Fehler ist eine Lernchance und hilft dem Algorithmus, dich besser zu unterstützen.
    4. **Nutze das Feedback:** Lies die KI-Hinweise aufmerksam, um dein Verständnis zu vertiefen.
    """)
