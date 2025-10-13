"""Submission management functions for HttpOnly Cookie support.

This module contains all submission-related database functions that have been
migrated to use the RPC pattern with session-based authentication.
"""

import streamlit as st
from typing import Optional, Dict, Any, List, Tuple
import uuid
from datetime import datetime
import json

from ..core.session import get_session_id, get_anon_client, handle_rpc_result


def create_submission(student_id: str, task_id: str, submission_data: dict | str) -> tuple[dict | None, str | None]:
    """Erstellt eine neue Einreichung in der Datenbank. Stößt KEINE KI an."""
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        if not student_id or not task_id or submission_data is None:
            return None, "Schüler-ID, Aufgaben-ID und Lösung sind erforderlich."

        submission_payload = submission_data
        if isinstance(submission_data, str):
            submission_payload = {"text": submission_data}
        
        # Convert submission_data to submission_text for RPC
        submission_text = json.dumps(submission_payload) if isinstance(submission_payload, dict) else submission_payload
        
        client = get_anon_client()
        result = client.rpc('create_submission', {
            'p_session_id': session_id,
            'p_task_id': task_id,
            'p_submission_text': submission_text
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Unbekannter Fehler')
            print(f"DB-Error creating submission: {error_msg}")
            return None, error_msg
        
        if result.data:
            # Parse JSON if it's a string, or return dict directly
            if isinstance(result.data, str):
                try:
                    return json.loads(result.data), None
                except json.JSONDecodeError:
                    return {"id": result.data}, None  # Fallback if it's just an ID
            else:
                return result.data, None
        else:
            return None, "Keine Daten zurückgegeben"
            
    except Exception as e:
        print(f"Exception in create_submission: {e}")
        return None, f"Fehler beim Erstellen der Einreichung: {str(e)}"


def get_remaining_attempts(student_id: str, task_id: str) -> tuple[int | None, int | None, str | None]:
    """Gibt zurück, wie viele Versuche noch übrig sind für eine Aufgabe.
    
    Returns:
        (remaining_attempts, max_attempts, error_message)
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return None, None, "Keine aktive Session gefunden"
        
        if not student_id or not task_id:
            return None, None, "Student-ID und Task-ID sind erforderlich."
        
        client = get_anon_client()
        result = client.rpc('get_remaining_attempts', {
            'p_session_id': session_id,
            'p_student_id': student_id,
            'p_task_id': task_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Unbekannter Fehler')
            return None, None, error_msg
        
        if result.data and len(result.data) > 0:
            # SQL function returns a table, get first row
            data = result.data[0]
            remaining = data.get('remaining_attempts')
            max_attempts = data.get('max_attempts')
            return remaining, max_attempts, None
        else:
            return None, None, "Keine Daten zurückgegeben"
            
    except Exception as e:
        print(f"Exception in get_remaining_attempts: {e}")
        return None, None, f"Fehler beim Abrufen der verbleibenden Versuche: {str(e)}"


def get_submission_for_task(student_id: str, task_id: str) -> tuple[dict | None, str | None]:
    """Holt die Einreichung eines Schülers für eine bestimmte Aufgabe.
    
    Returns:
        tuple: (Submission-Dict, None) bei Erfolg, (None, Fehlermeldung) bei Fehler oder wenn keine Einreichung existiert.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        if not student_id or not task_id:
            return None, "Student-ID und Task-ID sind erforderlich."
        
        client = get_anon_client()
        result = client.rpc('get_submission_for_task', {
            'p_session_id': session_id,
            'p_student_id': student_id,
            'p_task_id': task_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Unbekannter Fehler')
            return None, error_msg
        
        if result.data:
            # Handle both array and single object responses
            if isinstance(result.data, list) and len(result.data) > 0:
                return result.data[0], None
            elif isinstance(result.data, dict):
                return result.data, None
            else:
                return None, None
        else:
            return None, None
            
    except Exception as e:
        print(f"Exception in get_submission_for_task: {e}")
        return None, f"Fehler beim Abrufen der Submission: {str(e)}"


def update_submission_ai_results(
    submission_id: str, 
    criteria_analysis: str | None, 
    feedback: str | None, 
    rating_suggestion: str | None,
    feed_back_text: str | None = None,
    feed_forward_text: str | None = None
) -> tuple[bool, str | None]:
    """Aktualisiert eine Einreichung mit den Ergebnissen der KI.
       Verwendet die erweiterte RPC-Funktion für alle Felder.
       
       Args:
           submission_id: ID der Einreichung
           criteria_analysis: JSON-String der Kriterien-Analyse
           feedback: Kombiniertes Feedback (für Abwärtskompatibilität)
           rating_suggestion: Bewertungsvorschlag
           feed_back_text: Feed-Back Teil (Wo stehe ich?)
           feed_forward_text: Feed-Forward Teil (Nächste Schritte)
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        if not submission_id:
            return False, "Submission-ID fehlt."
        
        # Determine is_correct based on rating_suggestion
        is_correct = False
        if rating_suggestion and rating_suggestion.lower() in ['korrekt', 'richtig', 'correct', 'true']:
            is_correct = True
        
        # Use combined feedback or separate feed_back/feed_forward
        ai_feedback_text = feedback
        if not ai_feedback_text and (feed_back_text or feed_forward_text):
            parts = []
            if feed_back_text:
                parts.append(f"**Wo du stehst:**\n{feed_back_text}")
            if feed_forward_text:
                parts.append(f"**Nächste Schritte:**\n{feed_forward_text}")
            ai_feedback_text = "\n\n".join(parts)
        
        # Use extended RPC function that handles all fields
        client = get_anon_client()
        result = client.rpc('update_submission_ai_results_extended', {
            'p_session_id': session_id,
            'p_submission_id': submission_id,
            'p_is_correct': is_correct,
            'p_ai_feedback': ai_feedback_text,
            'p_criteria_analysis': criteria_analysis,
            'p_ai_grade': rating_suggestion,
            'p_feed_back_text': feed_back_text,
            'p_feed_forward_text': feed_forward_text
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = f"DB Fehler beim Aktualisieren der AI-Ergebnisse für Submission {submission_id}: {result.error.get('message', 'Unbekannter Fehler')}"
            print(error_msg)
            return False, error_msg
        
        return True, None
        
    except Exception as e:
        import traceback
        print(f"Exception in update_submission_ai_results: {traceback.format_exc()}")
        return False, f"Python Fehler beim Aktualisieren der AI-Ergebnisse für Submission {submission_id}: {e}"


def update_submission_teacher_override(submission_id: str, teacher_feedback: str | None, teacher_grade: str | None) -> tuple[bool, str | None]:
    """Aktualisiert eine Einreichung mit Lehrer-Feedback und/oder Bewertung.
    
    Args:
        submission_id: ID der Einreichung
        teacher_feedback: Lehrer-Feedback (None = nicht ändern)
        teacher_grade: Lehrer-Bewertung (None = nicht ändern)
    
    Returns:
        tuple: (True, None) bei Erfolg, (False, Fehlermeldung) bei Fehler.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        if not submission_id:
            return False, "Submission-ID ist erforderlich."
        
        # Determine override_grade boolean from teacher_grade string
        override_grade = False
        if teacher_grade and teacher_grade.lower() in ['korrekt', 'richtig', 'correct', 'true', 'yes', 'ja']:
            override_grade = True
        
        client = get_anon_client()
        result = client.rpc('update_submission_teacher_override', {
            'p_session_id': session_id,
            'p_submission_id': submission_id,
            'p_override_grade': override_grade,
            'p_teacher_feedback': teacher_feedback
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Unbekannter Fehler')
            return False, f"DB Fehler: {error_msg}"
        
        return True, None
        
    except Exception as e:
        import traceback
        print(f"Exception in update_submission_teacher_override: {traceback.format_exc()}")
        return False, f"Fehler beim Aktualisieren der Teacher-Override: {str(e)}"


def mark_feedback_as_viewed_safe(submission_id: str) -> tuple[bool, str]:
    """
    Markiert Feedback als gelesen mit expliziter Success-Verification.
    Verwendet die neue RPC-Funktion mit Session-basierter Authentifizierung.
    
    Args:
        submission_id: ID der Submission die als gelesen markiert werden soll
        
    Returns:
        Tuple (success: bool, error_message: str)
    """
    import traceback
    
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        if not submission_id:
            return False, "Submission-ID fehlt"
        
        client = get_anon_client()
        result = client.rpc('mark_feedback_as_viewed', {
            'p_session_id': session_id,
            'p_submission_id': submission_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = f"DB Fehler beim Markieren des Feedbacks: {result.error.get('message', 'Unbekannter Fehler')}"
            print(f"❌ {error_msg}")
            return False, error_msg
        
        # Check if update was successful (result.data should be True if row was updated)
        success = bool(result.data) if result.data is not None else False
        
        if success:
            print(f"✅ Feedback für Submission {submission_id} als gelesen markiert")
            return True, ""
        else:
            print(f"⚠️ Feedback für Submission {submission_id} konnte nicht markiert werden (evtl. bereits gelesen)")
            return False, "Feedback konnte nicht markiert werden"
        
    except Exception as e:
        error_msg = f"Exception beim Markieren des Feedbacks: {str(e)}"
        print(f"❌ {error_msg}\n{traceback.format_exc()}")
        return False, error_msg


def get_submission_history(student_id: str, task_id: str) -> tuple[list | None, str | None]:
    """Holt alle Einreichungen eines Schülers für eine Aufgabe, sortiert nach attempt_number."""
    try:
        session_id = get_session_id()
        if not session_id:
            return [], "Keine aktive Session gefunden"
        
        if not student_id or not task_id:
            return None, "Student-ID und Task-ID sind erforderlich."
        
        client = get_anon_client()
        result = client.rpc('get_submission_history', {
            'p_session_id': session_id,
            'p_student_id': student_id,
            'p_task_id': task_id
        }).execute()
        
        return handle_rpc_result(result, [])
    except Exception as e:
        import traceback
        print(f"Error in get_submission_history: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Historie: {str(e)}"


def get_submission_by_id(submission_id: str) -> tuple[dict | None, str | None]:
    """Holt eine einzelne Einreichung mit allen Details.
    
    Returns:
        tuple: (Submission-Dict, None) bei Erfolg, (None, Fehlermeldung) bei Fehler.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        if not submission_id:
            return None, "Submission-ID ist erforderlich."
        
        client = get_anon_client()
        result = client.rpc('get_submission_by_id', {
            'p_session_id': session_id,
            'p_submission_id': submission_id
        }).execute()
        
        data, error = handle_rpc_result(result, None)
        if error:
            return None, error
        
        # SQL function returns array, we need single item
        if isinstance(data, list) and len(data) > 0:
            return data[0], None
        elif isinstance(data, dict):
            return data, None
        else:
            return None, "Submission nicht gefunden."
    except Exception as e:
        import traceback
        print(f"Error in get_submission_by_id: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Submission: {str(e)}"


def get_submission_queue_position(submission_id: str) -> tuple[int | None, str | None]:
    """
    Ermittelt die Position einer Submission in der Feedback-Warteschlange.
    
    Returns:
        tuple: (Position in der Warteschlange, Fehlermeldung)
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        
        # Die existierende Funktion hat keine Session-Prüfung, 
        # aber sie liest nur öffentliche Daten (Queue-Position)
        result = client.rpc('get_submission_queue_position', {
            'p_submission_id': submission_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Abrufen der Queue-Position')
            return None, error_msg
        
        if result.data is not None:
            return result.data, None
        
        return None, "Queue-Position nicht verfügbar"
        
    except Exception as e:
        import traceback
        print(f"Error in get_submission_queue_position: {traceback.format_exc()}")
        return None, f"Fehler: {str(e)}"
