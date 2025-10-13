"""
Kurs-spezifisches Session State Management für Wissensfestiger.

Löst das Problem, dass bei Kurswechsel der Wissensfestiger-State verloren geht
und Feedback nicht mehr angezeigt wird. Implementiert kurs-isolierte Session-States
mit Legacy-Migration und Memory-Management.
"""

import streamlit as st
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta


class MasterySessionState:
    """
    Manager für kurs-spezifischen Wissensfestiger Session-State.
    
    Jeder Kurs erhält einen isolierten State-Container, wodurch Feedback
    und Task-Context bei Kurswechseln erhalten bleiben.
    """
    
    @staticmethod
    def get_course_state(course_id: str) -> Dict[str, Any]:
        """
        Ruft kurs-spezifischen State ab oder initialisiert ihn.
        
        Args:
            course_id: Eindeutige Kurs-ID
            
        Returns:
            Dict mit State-Keys: current_task, submission_id, last_answer, answer_submitted
        """
        if 'mastery_course_state' not in st.session_state:
            st.session_state.mastery_course_state = {}
        
        if course_id not in st.session_state.mastery_course_state:
            st.session_state.mastery_course_state[course_id] = {
                'current_task': None,
                'submission_id': None,
                'last_answer': None,
                'answer_submitted': False,
                'last_accessed': datetime.now()
            }
        else:
            # Update last_accessed timestamp
            st.session_state.mastery_course_state[course_id]['last_accessed'] = datetime.now()
        
        return st.session_state.mastery_course_state[course_id]
    
    @staticmethod
    def set_task(course_id: str, task: Dict[str, Any], submission_id: Optional[str] = None):
        """
        Setzt aktuelle Aufgabe für einen Kurs.
        
        Args:
            course_id: Kurs-ID
            task: Task-Objekt aus der Datenbank
            submission_id: Optional - ID einer bestehenden Submission (für Feedback-Anzeige)
        """
        state = MasterySessionState.get_course_state(course_id)
        state['current_task'] = task
        if submission_id:
            state['submission_id'] = submission_id
    
    @staticmethod
    def mark_submitted(course_id: str, answer: str, submission_id: str):
        """
        Markiert Aufgabe als eingereicht und speichert Kontext.
        
        Args:
            course_id: Kurs-ID
            answer: Eingereichte Antwort des Schülers
            submission_id: ID der erstellten Submission
        """
        state = MasterySessionState.get_course_state(course_id)
        state['answer_submitted'] = True
        state['last_answer'] = answer.strip()
        state['submission_id'] = submission_id
    
    @staticmethod
    def clear_task(course_id: str, keep_feedback_context: bool = True):
        """
        Bereinigt Task-spezifischen State für nächste Aufgabe.
        
        Args:
            course_id: Kurs-ID
            keep_feedback_context: Behält submission_id/last_answer für Feedback-Zuordnung
        """
        state = MasterySessionState.get_course_state(course_id)
        state['current_task'] = None
        state['answer_submitted'] = False
        
        if not keep_feedback_context:
            state['submission_id'] = None
            state['last_answer'] = None
    
    @staticmethod
    def clear_task_atomic(course_id: str, submission_id: str = None) -> bool:
        """
        Atomische Task-Bereinigung mit State-Verification.
        
        Args:
            course_id: Kurs-ID
            submission_id: Optional - wird für Debug-Logging verwendet
            
        Returns:
            bool: True wenn State erfolgreich bereinigt wurde
        """
        try:
            # 1. Pre-Clear State Backup
            state = MasterySessionState.get_course_state(course_id)
            backup_state = {
                'current_task': state.get('current_task'),
                'answer_submitted': state.get('answer_submitted'),
                'submission_id': state.get('submission_id'),
                'last_answer': state.get('last_answer')
            }
            
            print(f"🔄 Pre-Clear State für {course_id}: current_task={backup_state['current_task'] is not None}, answer_submitted={backup_state['answer_submitted']}")
            
            # 2. Bereinige State
            state['current_task'] = None
            state['answer_submitted'] = False
            state['submission_id'] = None
            state['last_answer'] = None
            
            # 3. Verification: State tatsächlich gecleart?
            if (state.get('current_task') is not None or 
                state.get('answer_submitted') is not False):
                # Restore backup bei Failure
                state.update(backup_state)
                print(f"❌ Session State Clear failed für course {course_id}")
                return False
                
            print(f"✅ Session State cleared für course {course_id}")
            return True
            
        except Exception as e:
            print(f"❌ Exception beim State Clear: {e}")
            return False
    
    @staticmethod
    def get_validated_submission_id(course_id: str) -> Optional[str]:
        """
        Validiert dass submission_id zum aktuellen Kurs gehört.
        
        Verhindert verwaiste Submission-IDs bei Kurswechseln.
        
        Args:
            course_id: Kurs-ID für Validation
            
        Returns:
            Validierte submission_id oder None
        """
        from utils.db_queries import get_submission_by_id
        
        state = MasterySessionState.get_course_state(course_id)
        submission_id = state.get('submission_id')
        
        if not submission_id:
            return None
            
        try:
            submission = get_submission_by_id(submission_id)
            if submission and submission.get('task', {}).get('course_id') == course_id:
                return submission_id
            else:
                # Bereinige verwaiste submission_id
                state['submission_id'] = None
                return None
        except Exception:
            # Bei DB-Fehlern: State bereinigen
            state['submission_id'] = None
            return None
    
    @staticmethod
    def cleanup_old_courses(active_course_ids: List[str], max_age_hours: int = 24):
        """
        Memory-Management: Entfernt alte Kurs-States.
        
        Args:
            active_course_ids: Liste der aktuell verfügbaren Kurse für den User
            max_age_hours: Maximales Alter für nicht-aktive Kurse
        """
        if 'mastery_course_state' not in st.session_state:
            return
            
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        courses_to_remove = []
        
        for course_id, state in st.session_state.mastery_course_state.items():
            # Entferne Kurse die nicht mehr aktiv sind UND alt sind
            if (course_id not in active_course_ids and 
                state.get('last_accessed', datetime.min) < cutoff_time):
                courses_to_remove.append(course_id)
        
        for course_id in courses_to_remove:
            del st.session_state.mastery_course_state[course_id]
    
    @staticmethod
    def migrate_legacy_session_state(selected_course_id: str):
        """
        Migriert alte Session-State-Keys zu kurs-spezifischem Format.
        
        Backward-Compatibility für bestehende User-Sessions.
        
        Args:
            selected_course_id: Aktuell ausgewählter Kurs für Migration
        """
        legacy_keys = [
            'current_mastery_task', 
            'mastery_submission_id',
            'last_mastery_answer', 
            'mastery_answer_submitted'
        ]
        
        # Prüfe ob Legacy-Keys existieren
        if not any(key in st.session_state for key in legacy_keys):
            return
            
        # Migriere zu neuem Format
        course_state = MasterySessionState.get_course_state(selected_course_id)
        
        if 'current_mastery_task' in st.session_state:
            course_state['current_task'] = st.session_state['current_mastery_task']
            
        if 'mastery_submission_id' in st.session_state:
            course_state['submission_id'] = st.session_state['mastery_submission_id']
            
        if 'last_mastery_answer' in st.session_state:
            course_state['last_answer'] = st.session_state['last_mastery_answer']
            
        if 'mastery_answer_submitted' in st.session_state:
            course_state['answer_submitted'] = st.session_state['mastery_answer_submitted']
        
        # Bereinige Legacy-Keys
        for key in legacy_keys:
            if key in st.session_state:
                del st.session_state[key]
        
        # Entferne auch den alten Kurs-Tracking-Key
        if 'last_selected_course_id' in st.session_state:
            del st.session_state['last_selected_course_id']
    
    @staticmethod
    def is_task_active_in_other_course(task_id: str, current_course_id: str) -> bool:
        """
        Prüft ob eine Task aktuell in einem anderen Kurs bearbeitet wird.
        
        Verhindert dass dieselbe Aufgabe in mehreren Kursen gleichzeitig angezeigt wird.
        
        Args:
            task_id: ID der zu prüfenden Aufgabe
            current_course_id: Aktueller Kurs (wird ausgeschlossen)
            
        Returns:
            True wenn Task in anderem Kurs aktiv ist
        """
        if 'mastery_course_state' not in st.session_state:
            return False
            
        for course_id, state in st.session_state.mastery_course_state.items():
            if course_id == current_course_id:
                continue
                
            current_task = state.get('current_task')
            if current_task and current_task.get('id') == task_id:
                # Zusätzlich prüfen ob Antwort submitted aber noch nicht completed
                if state.get('answer_submitted') and state.get('submission_id'):
                    return True
        
        return False
    
    @staticmethod  
    def get_state_summary() -> Dict[str, int]:
        """
        Debugging-Helper: Gibt Übersicht über Session-State.
        
        Returns:
            Dict mit Statistiken über aktuelle States
        """
        if 'mastery_course_state' not in st.session_state:
            return {'total_courses': 0}
            
        state_data = st.session_state.mastery_course_state
        return {
            'total_courses': len(state_data),
            'courses_with_tasks': sum(1 for s in state_data.values() if s.get('current_task')),
            'courses_with_submissions': sum(1 for s in state_data.values() if s.get('submission_id')),
            'courses_with_pending_answers': sum(1 for s in state_data.values() if s.get('answer_submitted'))
        }