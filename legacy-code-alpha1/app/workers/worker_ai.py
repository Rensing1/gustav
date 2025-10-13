"""
Worker-spezifische KI-Verarbeitungsfunktionen

Diese Funktionen sind vereinfachte Versionen der AI-Module für Worker-Nutzung
ohne Streamlit-Abhängigkeiten.
"""

import logging
import json
from typing import Dict, Any, Tuple, Optional
from supabase import Client

# Import AI modules
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.timeout_wrapper import with_timeout, TimeoutException
from workers.worker_db import (
    get_submission_details,
    get_task_details, 
    get_submission_history,
    update_submission_feedback,
    create_mastery_submission
)

# Import AI modules and ensure DSPy configuration is loaded on module level
# This prevents threading issues with DSPy config loading
from ai.feedback import FeedbackModule, CombinedMasteryFeedbackModule
from ai.config import ensure_lm_configured, reconfigure_lm
from ai.vision_processor import process_vision_submission_dspy
from ai.timeout_wrapper import with_timeout

logger = logging.getLogger(__name__)

def _ensure_dspy_configured():
    """Thread-safe check to ensure DSPy LM is configured"""
    if not ensure_lm_configured():
        logger.warning("DSPy LM not configured, attempting to reconfigure...")
        # Try to reload config
        try:
            success = reconfigure_lm()
            if not success:
                raise Exception("Failed to configure DSPy LM")
            logger.info("Successfully reconfigured DSPy LM")
        except Exception as e:
            raise Exception(f"Could not configure DSPy LM: {e}")
    return True


def process_regular_feedback(supabase: Client, submission_id: str) -> bool:
    """
    Verarbeitet reguläre Submission für Feedback-Generierung (Worker-Version).
    
    Args:
        supabase: Service-Role Supabase Client
        submission_id: UUID der Submission
        
    Returns:
        True bei Erfolg, False bei Fehler
    """
    try:
        logger.info(f"Processing regular feedback for submission {submission_id}")
        
        # 1. Lade Submission-Details
        submission = get_submission_details(supabase, submission_id)
        if not submission:
            raise Exception("Could not load submission details")
            
        student_id = submission['student_id']
        task_id = submission['task_id']
        submission_data = submission['submission_data']
        current_attempt = submission['attempt_number']
        
        # 2. Vision-Processing für File-Uploads (wenn file_path vorhanden)
        if submission_data.get('file_path'):
            logger.info(f"Processing vision for submission {submission_id}")
            # Vision-Processing mit Thread-basiertem Timeout wrappen
            @with_timeout(60)  # 60s Timeout für Vision-Processing (14-20s normal)
            def vision_with_timeout():
                return process_vision_submission_dspy(supabase, submission_data)
            
            submission_data = vision_with_timeout()
            
            # submission_data in DB updaten mit extrahiertem Text
            supabase.table('submission').update({
                'submission_data': submission_data
            }).eq('id', submission_id).execute()
            
            # Log processing metrics
            if submission_data.get('processing_metrics'):
                metrics = submission_data['processing_metrics']
                logger.info(f"Vision metrics for {submission_id}: download={metrics.get('download_time_ms')}ms, vision={metrics.get('vision_time_ms')}ms, total={metrics.get('total_time_ms')}ms")
            
        if not submission_data or not submission_data.get('text'):
            # Spezifischere Fehlermeldung
            if submission_data.get('processing_stage') == 'error':
                error = submission_data.get('processing_error', 'Unknown error')
                raise Exception(f"Vision processing failed: {error}")
            else:
                raise Exception("No submission text found")
            
        # 3. Lade Task-Details
        task_details = get_task_details(supabase, task_id)
        if not task_details:
            raise Exception("Could not load task details")
            
        # Assessment criteria sind optional - leere Liste ist ok
        assessment_criteria = task_details.get('assessment_criteria', [])
        if assessment_criteria is None:
            assessment_criteria = []
            
        # 4. Lade Submission-Historie für Kontext
        submission_history_str = "Kein vorheriger Versuch verfügbar."
        if current_attempt > 1:
            history = get_submission_history(supabase, student_id, task_id)
            if history and len(history) >= current_attempt - 1:
                previous_submission = history[current_attempt - 2]  # 0-indexed
                if previous_submission.get('submission_data', {}).get('text'):
                    submission_history_str = f"---\n{previous_submission['submission_data']['text']}\n---"
        
        # 5. Generiere KI-Feedback mit Timeout (nutzt AI_TIMEOUT env var)
        @with_timeout()
        def generate_feedback():
            # Ensure DSPy is configured before generating feedback
            _ensure_dspy_configured()
            
            feedback_module = FeedbackModule()
            return feedback_module(
                task_details=task_details,
                submission_text=submission_data["text"],
                submission_history=submission_history_str
            )
        
        logger.info(f"Generating AI feedback for submission {submission_id}")
        result = generate_feedback()
        
        # 6. Speichere Ergebnisse
        combined_feedback = f"{result['feed_back_text']}\n\n{result['feed_forward_text']}"
        
        criteria_analysis = json.dumps({
            "analysis_text": result["analysis"],
            "method": "worker_v1"
        }, ensure_ascii=False)
        
        success = update_submission_feedback(
            supabase=supabase,
            submission_id=submission_id,
            feedback=combined_feedback,
            criteria_analysis=criteria_analysis,
            feed_back_text=result["feed_back_text"],
            feed_forward_text=result["feed_forward_text"]
        )
        
        if success:
            logger.info(f"Successfully processed regular feedback for submission {submission_id}")
            return True
        else:
            raise Exception("Failed to update submission in database")
            
    except TimeoutException:
        logger.error(f"Timeout processing regular feedback for submission {submission_id}")
        update_submission_feedback(
            supabase=supabase,
            submission_id=submission_id,
            feedback="Die Feedback-Generierung dauerte zu lange. Bitte versuche es später erneut."
        )
        return False
        
    except Exception as e:
        logger.error(f"Error processing regular feedback for submission {submission_id}: {e}")
        # Mark as failed for retry
        try:
            supabase.rpc('mark_feedback_failed', {
                'p_submission_id': submission_id,
                'p_error_message': f"Fehler bei Feedback-Generierung: {str(e)}"
            }).execute()
        except Exception as db_error:
            logger.error(f"Failed to mark submission as failed: {db_error}")
        return False


def process_mastery_feedback(supabase: Client, submission_id: str, submission_data: Dict[str, Any], task_id: str, student_id: str) -> bool:
    """
    Verarbeitet Mastery-Submission für Bewertung und Feedback (Worker-Version).
    
    Args:
        supabase: Service-Role Supabase Client
        submission_id: UUID der Submission
        submission_data: Submission-Daten
        task_id: UUID der Task
        student_id: UUID des Schülers
        
    Returns:
        True bei Erfolg, False bei Fehler
    """
    try:
        logger.info(f"Processing mastery feedback for submission {submission_id}")
        
        # 1. Extrahiere Antwort
        answer = submission_data.get('answer', submission_data.get('text', ''))
        if not answer:
            raise Exception("No answer found in mastery submission")
            
        # 2. Lade Task-Details
        task_details = get_task_details(supabase, task_id)
        if not task_details:
            raise Exception("Could not load task details")
            
        # 3. Lade Historie für Kontext
        submission_history_str = "Dies ist der erste Versuch für diese Aufgabe."
        history = get_submission_history(supabase, student_id, task_id)
        if history:
            last_submission = history[-1]
            if last_submission.get('submission_data', {}).get('text'):
                submission_history_str = f"---\n{last_submission['submission_data']['text']}\n---"
        
        # 4. Generiere KI-Bewertung mit Timeout (nutzt AI_TIMEOUT env var)
        @with_timeout()
        def generate_mastery_feedback():
            # Ensure DSPy is configured before generating mastery feedback
            _ensure_dspy_configured()
            
            ai_module = CombinedMasteryFeedbackModule()
            return ai_module(
                task_details=task_details,
                student_answer=answer,
                submission_history=submission_history_str
            )
        
        logger.info(f"Generating AI mastery feedback for submission {submission_id}")
        ai_result = generate_mastery_feedback()
        
        q_vec = ai_result.get("q_vec")
        if not q_vec:
            raise Exception("No q_vec received from AI evaluation")
        
        # 5. Speichere in regulärer submission-Tabelle (für Queue-Kompatibilität)
        success = update_submission_feedback(
            supabase=supabase,
            submission_id=submission_id,
            feedback=ai_result.get('feedback', 'Mastery-Feedback generiert'),
            feed_back_text=ai_result.get('feed_back_text'),
            feed_forward_text=ai_result.get('feed_forward_text')
        )
        
        # 6. Zusätzlich: Aktualisiere mit Mastery-spezifischen Daten
        if success:
            try:
                # Store mastery score directly in ai_insights for UI consumption
                ai_insights_data = dict(ai_result)
                ai_insights_data['mastery_score'] = q_vec.get('korrektheit', 0)
                
                supabase.table('submission').update({
                    'ai_insights': ai_insights_data
                }).eq('id', submission_id).execute()
            except Exception as mastery_update_error:
                logger.warning(f"Failed to update mastery-specific data: {mastery_update_error}")
        
        # 7. Aktualisiere Mastery-Progress für Spaced Repetition
        if success:
            try:
                from utils.db_queries import _update_mastery_progress
                mastery_success, mastery_error = _update_mastery_progress(
                    student_id=student_id,
                    task_id=task_id,
                    q_vec=q_vec,
                    service_client=supabase
                )
                if not mastery_success:
                    logger.warning(f"Mastery progress update failed: {mastery_error}")
                else:
                    logger.info(f"Updated mastery progress for task {task_id}")
            except Exception as mastery_err:
                logger.error(f"Error updating mastery progress: {mastery_err}")
        
        if success:
            logger.info(f"Successfully processed mastery feedback for submission {submission_id}")
            return True
        else:
            raise Exception("Failed to update submission in database")
            
    except TimeoutException:
        logger.error(f"Timeout processing mastery feedback for submission {submission_id}")
        update_submission_feedback(
            supabase=supabase,
            submission_id=submission_id,
            feedback="Die Mastery-Auswertung dauerte zu lange. Bitte versuche es später erneut."
        )
        return False
        
    except Exception as e:
        logger.error(f"Error processing mastery feedback for submission {submission_id}: {e}")
        # Mark as failed for retry
        try:
            supabase.rpc('mark_feedback_failed', {
                'p_submission_id': submission_id,
                'p_error_message': f"Fehler bei Mastery-Auswertung: {str(e)}"
            }).execute()
        except Exception as db_error:
            logger.error(f"Failed to mark submission as failed: {db_error}")
        return False