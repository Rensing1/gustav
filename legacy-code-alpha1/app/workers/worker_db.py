"""
Worker-spezifische DB-Queries

Diese Funktionen sind speziell für den Feedback-Worker designed und nutzen
den Service-Role-Client direkt ohne RLS oder Streamlit-Abhängigkeiten.
"""

import logging
from typing import Optional, Dict, Any, Tuple
from supabase import Client

logger = logging.getLogger(__name__)


def get_submission_details(supabase: Client, submission_id: str) -> Optional[Dict[str, Any]]:
    """
    Holt Submission-Details für Worker-Verarbeitung.
    
    Args:
        supabase: Service-Role Supabase Client
        submission_id: UUID der Submission
        
    Returns:
        Dict mit Submission-Details oder None bei Fehler
    """
    try:
        result = supabase.table('submission').select(
            'id, student_id, task_id, submission_data, attempt_number, created_at'
        ).eq('id', submission_id).single().execute()
        
        if result.data:
            logger.debug(f"Retrieved submission details for {submission_id}")
            return result.data
        else:
            logger.warning(f"No submission found for ID {submission_id}")
            return None
            
    except Exception as e:
        logger.error(f"Error retrieving submission {submission_id}: {e}")
        return None


def get_task_details(supabase: Client, task_id: str) -> Optional[Dict[str, Any]]:
    """
    Holt Task-Details für KI-Verarbeitung.
    
    Args:
        supabase: Service-Role Supabase Client
        task_id: UUID der Task
        
    Returns:
        Dict mit Task-Details oder None bei Fehler
    """
    try:
        # Phase 4: Use views instead of old task table
        # First try regular tasks
        result = supabase.table('all_regular_tasks').select(
            'id, instruction, assessment_criteria, solution_hints, is_mastery'
        ).eq('id', task_id).execute()
        
        if result.data and len(result.data) > 0:
            logger.debug(f"Retrieved regular task details for {task_id}")
            return result.data[0]
            
        # If not found, try mastery tasks
        result = supabase.table('all_mastery_tasks').select(
            'id, instruction, assessment_criteria, solution_hints, is_mastery'
        ).eq('id', task_id).execute()
        
        if result.data and len(result.data) > 0:
            logger.debug(f"Retrieved mastery task details for {task_id}")
            return result.data[0]
        else:
            logger.warning(f"No task found for ID {task_id}")
            return None
            
    except Exception as e:
        logger.error(f"Error retrieving task {task_id}: {e}")
        return None


def get_submission_history(supabase: Client, student_id: str, task_id: str) -> list:
    """
    Holt vorherige Submissions eines Schülers für eine Aufgabe.
    
    Args:
        supabase: Service-Role Supabase Client
        student_id: UUID des Schülers
        task_id: UUID der Task
        
    Returns:
        Liste der vorherigen Submissions (chronologisch sortiert)
    """
    try:
        result = supabase.table('submission').select(
            'id, submission_data, attempt_number, created_at'
        ).eq('student_id', student_id).eq('task_id', task_id).order('created_at').execute()
        
        if result.data:
            logger.debug(f"Retrieved {len(result.data)} submission(s) for student {student_id}, task {task_id}")
            return result.data
        else:
            logger.debug(f"No submission history for student {student_id}, task {task_id}")
            return []
            
    except Exception as e:
        logger.error(f"Error retrieving submission history: {e}")
        return []


def update_submission_feedback(
    supabase: Client, 
    submission_id: str, 
    feedback: str,
    criteria_analysis: Optional[str] = None,
    feed_back_text: Optional[str] = None,
    feed_forward_text: Optional[str] = None,
    rating_suggestion: Optional[str] = None
) -> bool:
    """
    Aktualisiert Submission mit KI-Feedback (Worker-Version).
    
    Args:
        supabase: Service-Role Supabase Client
        submission_id: UUID der Submission
        feedback: Hauptfeedback-Text
        criteria_analysis: Optionale Kriterien-Analyse
        feed_back_text: Optionaler Feed-Back Text
        feed_forward_text: Optionaler Feed-Forward Text
        rating_suggestion: Optionale Bewertungsempfehlung
        
    Returns:
        True bei Erfolg, False bei Fehler
    """
    try:
        update_data = {
            'ai_feedback': feedback,
            'feedback_status': 'completed'
        }
        
        # Optionale Felder nur setzen wenn vorhanden
        if criteria_analysis:
            update_data['ai_criteria_analysis'] = criteria_analysis
        if feed_back_text:
            update_data['feed_back_text'] = feed_back_text
        if feed_forward_text:
            update_data['feed_forward_text'] = feed_forward_text
        if rating_suggestion:
            update_data['ai_grade'] = rating_suggestion
            
        result = supabase.table('submission').update(update_data).eq('id', submission_id).execute()
        
        if hasattr(result, 'error') and result.error:
            logger.error(f"Database error updating submission {submission_id}: {result.error}")
            return False
            
        logger.info(f"Successfully updated feedback for submission {submission_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating submission feedback {submission_id}: {e}")
        return False


def create_mastery_submission(
    supabase: Client,
    student_id: str,
    task_id: str,
    answer: str,
    q_vec: Dict[str, Any],
    ai_feedback: str
) -> Tuple[Optional[str], Optional[str]]:
    """
    Erstellt eine Mastery-Submission (Worker-Version).
    
    Args:
        supabase: Service-Role Supabase Client
        student_id: UUID des Schülers
        task_id: UUID der Task
        answer: Schülerantwort
        q_vec: Bewertungsvektor
        ai_feedback: KI-Feedback
        
    Returns:
        Tuple (submission_id, error_message)
    """
    try:
        submission_data = {
            "student_id": student_id,
            "task_id": task_id,
            "submission_data": {"text": answer},
            "ai_criteria_analysis": q_vec,
            "ai_feedback": ai_feedback,
            "feedback_status": "completed"
        }
        
        result = supabase.table('mastery_submission').insert(submission_data).execute()
        
        if hasattr(result, 'error') and result.error:
            logger.error(f"Database error creating mastery submission: {result.error}")
            return None, str(result.error)
            
        if result.data and len(result.data) > 0:
            submission_id = result.data[0].get('id')
            logger.info(f"Successfully created mastery submission {submission_id}")
            return submission_id, None
        else:
            logger.error("No data returned from mastery submission insert")
            return None, "No data returned from insert"
            
    except Exception as e:
        logger.error(f"Error creating mastery submission: {e}")
        return None, str(e)