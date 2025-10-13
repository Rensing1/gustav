"""Mastery and spaced repetition functions for HttpOnly Cookie support.

This module contains all mastery learning and spaced repetition functions
that have been migrated to use the RPC pattern with session-based authentication.
"""

import json
import traceback
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple

from ..core.session import get_session_id, get_anon_client, handle_rpc_result


def get_mastery_tasks_for_course(course_id: str) -> tuple[list | None, str | None]:
    """
    Holt alle Mastery-Aufgaben für einen Kurs mit Studentenfortschritt.
    Nutzt RPC für Session-basierte Authentifizierung.
    
    Returns:
        tuple: (Liste von Aufgaben mit Fortschritt, Fehlermeldung)
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('get_mastery_tasks_for_course', {
            'p_session_id': session_id,
            'p_course_id': course_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Abrufen der Mastery-Aufgaben')
            return None, error_msg
        
        # Map RPC results to expected format
        tasks = []
        for row in (result.data or []):
            task = {
                'id': row['task_id'],
                'instruction': row.get('instruction', ''),  # Use instruction directly
                'title': row.get('title', ''),  # Use title directly
                'section_id': row.get('section_id'),
                'section_title': row.get('section_title', ''),
                'unit_id': row.get('unit_id'),
                'unit_title': row.get('unit_title', ''),
                'difficulty_level': row.get('difficulty_level', 1),
                'solution_hints': row.get('solution_hints', ''),  # Changed from concept_explanation
                'student_progress': row.get('student_progress', {}),  # May not be returned by current RPC
                # Add unit_section for compatibility
                'unit_section': {
                    'title': row.get('section_title', ''),
                    'unit_id': row.get('unit_id')
                }
            }
            tasks.append(task)
        
        return tasks, None
        
    except Exception as e:
        print(f"Error in get_mastery_tasks_for_course: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Mastery-Aufgaben: {str(e)}"


def get_next_due_mastery_task(student_id: str, course_id: str) -> tuple[dict | None, str | None]:
    """
    Holt die nächste fällige Mastery-Aufgabe für einen Schüler.
    Prüft welche Aufgabe als nächstes bearbeitet werden sollte.
    
    Returns:
        tuple: (Nächste Aufgabe oder None, Fehlermeldung)
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('get_next_due_mastery_task', {
            'p_session_id': session_id,
            'p_student_id': student_id,
            'p_course_id': course_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            return None, result.error.get('message', 'Fehler beim Abrufen der nächsten Aufgabe')
        
        if result.data and len(result.data) > 0:
            task_data = result.data[0]
            return {
                'id': task_data['task_id'],
                'title': task_data.get('instruction', ''),  # Use instruction as title
                'instruction': task_data.get('instruction', ''),
                'section_id': task_data.get('section_id'),
                'unit_id': task_data.get('unit_id'),
                'section_title': task_data.get('section_title', ''),
                'unit_title': task_data.get('unit_title', ''),
                'difficulty_level': task_data.get('difficulty_level', 1),
                'solution_hints': task_data.get('solution_hints', ''),
                'total_attempts': task_data.get('total_attempts', 0),
                'correct_attempts': task_data.get('correct_attempts', 0),
                'days_since_last_attempt': task_data.get('days_since_last_attempt'),
                'priority_score': task_data.get('priority_score', 0)
            }, None
        
        return None, None  # Keine fällige Aufgabe
        
    except Exception as e:
        print(f"Error in get_next_due_mastery_task: {traceback.format_exc()}")
        return None, f"Fehler: {str(e)}"


def get_next_mastery_task_or_unviewed_feedback(student_id: str, course_id: str) -> dict:
    """
    Prüft ob es ungelesenes Feedback oder eine fällige Aufgabe gibt.
    Nutzt die neue RPC-Funktion, die JSON zurückgibt.
    
    Returns:
        dict: {
            'type': 'feedback' | 'task' | 'no_tasks',
            'task': dict | None,
            'submission': dict | None,
            'error': str | None
        }
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return {
                'type': 'error',
                'task': None,
                'submission': None,
                'error': "Keine aktive Session gefunden"
            }
        
        client = get_anon_client()
        result = client.rpc('get_next_mastery_task_or_unviewed_feedback', {
            'p_session_id': session_id,
            'p_student_id': student_id,
            'p_course_id': course_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            return {
                'type': 'error',
                'task': None,
                'submission': None,
                'error': result.error.get('message', 'Fehler bei der Abfrage')
            }
        
        if result.data:
            # Die neue RPC-Funktion gibt direkt JSON zurück
            data = result.data
            
            if data.get('type') == 'feedback':
                # Ungelesenes Feedback gefunden
                return {
                    'type': 'show_feedback',
                    'task': {
                        'id': data['task_id'],
                        'instruction': data['task_instruction'],
                        'title': data['task_title'],
                        'section_id': data['section_id'],
                        'section_title': data['section_title'],
                        'unit_id': data['unit_id'],
                        'unit_title': data['unit_title'],
                        'difficulty_level': data['difficulty_level'],
                        'solution_hints': data['solution_hints'],
                        'mastery_progress': data.get('mastery_progress')  # Include mastery progress for UI display
                    },
                    'submission': {
                        'id': data['submission_id'],
                        'submitted_at': data['submitted_at'],
                        'is_correct': data['is_correct'],
                        'submission_text': data['submission_text'],
                        'ai_feedback': data['ai_feedback'],
                        'ai_grade': data.get('ai_grade'),
                        'teacher_feedback': data.get('teacher_feedback'),
                        'teacher_grade': data.get('teacher_grade'),
                        'feed_back_text': data.get('feed_back_text'),
                        'feed_forward_text': data.get('feed_forward_text')
                    },
                    'error': None
                }
            elif data.get('type') == 'task':
                # Nächste fällige Aufgabe
                return {
                    'type': 'new_task',
                    'task': {
                        'id': data['task_id'],
                        'instruction': data['task_instruction'],
                        'title': data['task_title'],
                        'section_id': data['section_id'],
                        'section_title': data['section_title'],
                        'unit_id': data['unit_id'],
                        'unit_title': data['unit_title'],
                        'difficulty_level': data['difficulty_level'],
                        'solution_hints': data['solution_hints'],
                        'last_attempt': data.get('last_attempt'),
                        'correct_attempts': data.get('correct_attempts', 0),
                        'total_attempts': data.get('total_attempts', 0),
                        'next_review_date': data.get('next_review_date'),
                        'priority_score': data.get('priority_score'),
                        'mastery_progress': data.get('mastery_progress')  # Include mastery progress for UI display
                    },
                    'submission': None,
                    'error': None
                }
            elif data.get('type') == 'no_tasks':
                # Keine weiteren Aufgaben
                return {
                    'type': 'no_tasks',
                    'task': None,
                    'submission': None,
                    'error': data.get('message', 'Keine weiteren Aufgaben verfuegbar')
                }
        
        # Unerwartetes Datenformat
        return {
            'type': 'error',
            'task': None,
            'submission': None,
            'error': "Unerwartetes Datenformat von der API"
        }
        
    except Exception as e:
        print(f"Error in get_next_mastery_task_or_unviewed_feedback: {traceback.format_exc()}")
        return {
            'type': 'error',
            'task': None,
            'submission': None,
            'error': f"Fehler: {str(e)}"
        }


def save_mastery_submission(student_id: str, task_id: str, answer: str, assessment: dict) -> tuple[dict | None, str | None]:
    """
    Speichert eine Mastery-Einreichung mit KI-Assessment.
    Wird typischerweise von submit_mastery_answer aufgerufen.
    
    Returns:
        tuple: (Gespeicherte Submission, Fehlermeldung)
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('save_mastery_submission', {
            'p_session_id': session_id,
            'p_task_id': task_id,
            'p_submission_text': json.dumps({"text": answer}),
            'p_ai_assessment': json.dumps(assessment)
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Speichern der Submission')
            return None, error_msg
        
        if result.data:
            return result.data, None
        
        return None, "Unerwartete Antwort beim Speichern der Submission"
        
    except Exception as e:
        print(f"Error in save_mastery_submission: {traceback.format_exc()}")
        return None, f"Fehler beim Speichern: {str(e)}"


def submit_mastery_answer(student_id: str, task_id: str, answer: str) -> tuple[dict | None, str | None]:
    """
    Verarbeitet eine Wissensfestiger-Antwort: KI-Bewertung & Feedback, Speicherung, Fortschritts-Update.
    Nutzt jetzt RPC für alle Datenbankoperationen.
    """
    from ai.feedback import CombinedMasteryFeedbackModule
    from ..content.tasks import get_task_details
    from .submissions import get_submission_history
    
    try:
        # 1. Hole Aufgabendetails für die KI
        task_details, error = get_task_details(task_id)
        if error or not task_details:
            return None, error or f"Aufgabe nicht gefunden: {task_id}"

        # 2. Lade Submission-Historie (letzter Versuch)
        submission_history_str = "Dies ist der erste Versuch für diese Aufgabe."
        history, error = get_submission_history(student_id, task_id)
        if error:
            print(f"WARNUNG: Konnte Submission-Historie nicht laden: {error}")
        elif history:
            last_submission = history[-1]
            solution_text = last_submission.get("submission_data", {}).get("text", "(Kein Text)")
            submission_history_str = f"---\n{solution_text}\n---"

        # 3. Generiere kombinierte KI-Bewertung und pädagogisches Feedback
        ai_module = CombinedMasteryFeedbackModule()
        ai_result = ai_module(
            task_details=task_details,
            student_answer=answer,
            submission_history=submission_history_str
        )
        
        q_vec = ai_result.get("q_vec")
        if not q_vec:
            return None, "Fehler bei der KI-Bewertung, kein q_vec erhalten."

        # 4. Speichere die Einreichung mit allen KI-Ergebnissen via RPC
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        
        # Build assessment object for RPC
        assessment = {
            "q_vec": q_vec,
            "feed_back_text": ai_result.get("feed_back_text"),
            "feed_forward_text": ai_result.get("feed_forward_text"),
            "ai_feedback": f"{ai_result.get('feed_back_text')}\n\n{ai_result.get('feed_forward_text')}"
        }
        
        # Use RPC to save submission and update progress atomically
        result = client.rpc('submit_mastery_answer_complete', {
            'p_session_id': session_id,
            'p_task_id': task_id,
            'p_submission_text': json.dumps({"text": answer}),
            'p_ai_assessment': json.dumps(assessment),
            'p_q_vec': json.dumps(q_vec)
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Verarbeiten der Antwort')
            return None, error_msg
        
        # 5. Gib das vollständige KI-Ergebnis an die UI zurück
        return ai_result, None

    except Exception as e:
        print(f"Traceback in submit_mastery_answer: {traceback.format_exc()}")
        return None, f"Fehler bei der Verarbeitung der Antwort: {e}"


def get_mastery_stats_for_student(student_id: str, course_id: str) -> tuple[dict | None, str | None]:
    """
    Holt Wissensfestiger-Statistiken für einen Schüler in einem Kurs.
    
    Returns:
        tuple: (Statistik-Dict, Fehlermeldung)
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('get_mastery_stats_for_student', {
            'p_session_id': session_id,
            'p_student_id': student_id,
            'p_course_id': course_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Abrufen der Statistiken')
            return None, error_msg
        
        if result.data and len(result.data) > 0:
            stats_data = result.data[0]
            return {
                'total_tasks': stats_data['total_tasks'],
                'completed_tasks': stats_data['completed_tasks'],
                'due_today': stats_data['due_today'],
                'overdue': stats_data['overdue'],
                'upcoming': stats_data['upcoming'],
                'completion_rate': stats_data['completion_rate'],
                'average_rating': stats_data['average_rating'],
                'streak_days': stats_data.get('streak_days', 0)
            }, None
        
        # No data - return empty stats
        return {
            'total_tasks': 0,
            'completed_tasks': 0,
            'due_today': 0,
            'overdue': 0,
            'upcoming': 0,
            'completion_rate': 0.0,
            'average_rating': 0.0,
            'streak_days': 0
        }, None
        
    except Exception as e:
        print(f"Error in get_mastery_stats_for_student: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Statistiken: {str(e)}"


def get_mastery_overview_for_teacher(course_id: int) -> tuple[list | None, str | None]:
    """
    Holt Wissensfestiger-Übersicht für Lehrer mit Fortschritt aller Schüler.
    
    Returns:
        tuple: (Liste von Schüler-Fortschritten, Fehlermeldung)
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('get_mastery_overview_for_teacher', {
            'p_session_id': session_id,
            'p_course_id': str(course_id)  # Convert to string for consistency
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Abrufen der Übersicht')
            return None, error_msg
        
        # Map results to expected format
        overview = []
        for student_data in (result.data or []):
            overview.append({
                'student_id': student_data['student_id'],
                'student_name': student_data['student_name'],
                'student_email': student_data['student_email'],
                'total_tasks': student_data['total_tasks'],
                'completed_tasks': student_data['completed_tasks'],
                'overdue_tasks': student_data['overdue_tasks'],
                'tasks_due_today': student_data['tasks_due_today'],
                'upcoming_tasks': student_data['upcoming_tasks'],
                'completion_percentage': student_data['completion_percentage'],
                'average_difficulty': student_data['average_difficulty'],
                'last_activity': student_data['last_activity']
            })
        
        return overview, None
        
    except Exception as e:
        print(f"Error in get_mastery_overview_for_teacher: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Übersicht: {str(e)}"


def get_mastery_progress_summary(student_id: str, course_id: str) -> tuple[dict | None, str | None]:
    """
    Optimierte Funktion für kompakte Mastery-Statistiken.
    Holt alle benötigten Daten über existierende RPC-Funktionen.
    
    Returns:
        tuple: (Flaches Dict mit Mastery-Statistiken, Fehlermeldung)
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        
        # Haupt-Statistiken über existierende RPC
        result = client.rpc('get_mastery_summary', {
            'p_session_id': session_id,  # Session ID hinzugefügt
            'p_student_id': student_id,
            'p_course_id': course_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Abrufen der Statistiken')
            return None, error_msg
        
        if not result.data or len(result.data) == 0:
            # Fallback auf Standard-Werte wenn keine Daten
            return {
                'total': 0,
                'mastered': 0,
                'learning': 0,
                'not_started': 0,
                'due_today': 0,
                'avg_stability': 0.0,
                'streak': 0,
                'due_tomorrow': 0
            }, None
            
        stats = result.data[0]
        
        # Debug: Log was wir von get_mastery_summary bekommen
        print(f"DEBUG mastery.py: stats von get_mastery_summary = {stats}")
        
        # Streak berechnen über existierende RPC
        streak_result = client.rpc('calculate_learning_streak', {
            'p_session_id': session_id,
            'p_student_id': student_id
        }).execute()
        
        print(f"DEBUG mastery.py: streak_result.data = {streak_result.data}")
        
        if streak_result.data and len(streak_result.data) > 0:
            stats['streak'] = streak_result.data[0].get('current_streak', 0)
        else:
            stats['streak'] = 0
            
        print(f"DEBUG mastery.py: stats['streak'] = {stats['streak']}, type = {type(stats['streak'])}")
        
        # Morgen fällige Aufgaben über existierende RPC
        tomorrow_result = client.rpc('get_due_tomorrow_count', {
            'p_session_id': session_id,  # Session ID hinzugefügt
            'p_student_id': student_id,
            'p_course_id': course_id
        }).execute()
        
        # tomorrow_result.data ist die direkte Zahl von der RPC-Funktion
        if tomorrow_result.data is not None:
            stats['due_tomorrow'] = tomorrow_result.data
        else:
            stats['due_tomorrow'] = 0
        
        return stats, None
        
    except Exception as e:
        print(f"Error in get_mastery_progress_summary: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Statistiken: {str(e)}"


def _update_mastery_progress(student_id: str, task_id: str, q_vec: dict) -> tuple[bool, str | None]:
    """
    Aktualisiert den Lernfortschritt nach einer Mastery-Submission.
    Nutzt jetzt RPC statt Service Client.
    
    HINWEIS: Diese Funktion wird jetzt automatisch von submit_mastery_answer_complete RPC aufgerufen.
    Sie bleibt hier nur für Rückwärtskompatibilität.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('update_mastery_progress', {
            'p_session_id': session_id,
            'p_student_id': student_id,
            'p_task_id': task_id,
            'p_q_vec': json.dumps(q_vec)
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Aktualisieren des Fortschritts')
            return False, error_msg
        
        return True, None
        
    except Exception as e:
        print(f"Error in _update_mastery_progress: {traceback.format_exc()}")
        return False, f"Fehler beim Aktualisieren des Fortschritts: {str(e)}"