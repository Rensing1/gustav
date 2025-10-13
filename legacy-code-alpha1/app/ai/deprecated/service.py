# app/ai/service.py

import dspy
import traceback
import os
import sys

# --- Pfad-Anpassung (bleibt wichtig) ---
current_dir_service = os.path.dirname(os.path.abspath(__file__))
app_dir_service = os.path.dirname(current_dir_service)
if app_dir_service not in sys.path:
    sys.path.insert(0, app_dir_service)

# Importiere DB-Funktionen und das Programm
from utils.db_queries import get_task_details, update_submission_ai_results
# Nutzt jetzt analyze_submission statt process_submission_with_atomic_analysis
from .processor import analyze_submission
# Importiere das Setup-Modul, um das konfigurierte LM zu holen
from . import dspy_setup # Führt setup_global_lm() beim Import aus

def generate_ai_insights_for_submission(submission_id: str, submission_data: dict, task_id: str):
    """
    Generiert KI-Feedback durch die holistische Analyse-Pipeline.
    """
    print(f"\n--- Starte KI-Feedback-Generierung (holistische Analyse) für Submission ID: {submission_id} ---")

    # 1. LM-Instanz prüfen
    lm_instance = dspy_setup._lm_globally_configured
    if not lm_instance:
        print(f"FEHLER: Globales LM nicht konfiguriert. Breche KI-Verarbeitung ab für {submission_id}.")
        update_submission_ai_results(
            submission_id=submission_id,
            criteria_analysis=None,
            feedback="Fehler: KI-System nicht verfügbar.",
            rating_suggestion=None,
            feed_back_text=None,
            feed_forward_text=None
        )
        return

    # 2. Aufgaben-Details holen
    task_details, error_task = get_task_details(task_id)
    if error_task or not task_details:
        print(f"FEHLER: Task-Details nicht geladen für {task_id}: {error_task}")
        update_submission_ai_results(
            submission_id=submission_id,
            criteria_analysis=None,
            feedback="Fehler: Aufgabe konnte nicht geladen werden.",
            rating_suggestion=None,
            feed_back_text=None,
            feed_forward_text=None
        )
        return

    # 3. Holistische Analyse verwenden
    feedback_result, error = analyze_submission(
        submission_id=submission_id,
        task_details=task_details,
        submission_data=submission_data
    )

    if error:
        print(f"FEHLER in holistischer Analyse: {error}")
        # Speichere Fehlermeldung
        update_submission_ai_results(
            submission_id=submission_id,
            criteria_analysis=None,
            feedback=f"Fehler bei der Feedback-Generierung: {error}",
            rating_suggestion=None,
            feed_back_text=None,
            feed_forward_text=None
        )
        return

    # 4. Erfolgreiche Ergebnisse speichern
    print(f"Speichere strukturiertes Feedback für Submission {submission_id} in DB...")
    
    # Kombiniere Feed-Back und Feed-Forward für Abwärtskompatibilität
    combined_feedback = f"{feedback_result['feed_back_text']}\n\n{feedback_result['feed_forward_text']}"
    
    success_update, error_update = update_submission_ai_results(
        submission_id=submission_id,
        criteria_analysis=feedback_result.get('criteria_analysis'),
        feedback=combined_feedback,  # Für Abwärtskompatibilität
        rating_suggestion=None,
        feed_back_text=feedback_result.get('feed_back_text'),
        feed_forward_text=feedback_result.get('feed_forward_text')
    )
    
    if success_update:
        print(f"✓ Feedback erfolgreich gespeichert für Submission {submission_id}")
    else:
        print(f"! Fehler beim Speichern: {error_update}")

    print(f"--- KI-Feedback-Generierung (holistische Analyse) für Submission ID: {submission_id} abgeschlossen ---")


def generate_mastery_assessment(task_details: dict, student_answer: str) -> dict:
    """
    Generiert eine numerische Bewertung (1-5) für eine Mastery-Aufgabe.
    
    Args:
        task_details: Dictionary mit task_instruction, assessment_criteria, solution_hints
        student_answer: Die Antwort des Schülers
        
    Returns:
        Dictionary mit 'score' (int 1-5) und 'reasoning' (str)
    """
    print(f"\n--- Starte Mastery-Bewertung ---")
    
    # Import the signature and program
    from .signatures import MasteryAssessment
    from .programs import MasteryAssessor
    
    # Check if LM is configured
    lm_instance = dspy_setup._lm_globally_configured
    if not lm_instance:
        print("FEHLER: Globales LM nicht konfiguriert.")
        return {
            'score': 1,
            'reasoning': 'KI-System nicht verfügbar'
        }
    
    try:
        # Create assessor instance
        assessor = MasteryAssessor()
        
        # Prepare inputs
        task_instruction = task_details.get('instruction', '')
        assessment_criteria = task_details.get('assessment_criteria', [])
        solution_hints = task_details.get('solution_hints', '')
        
        # Convert criteria to string if it's a list
        if isinstance(assessment_criteria, list):
            import json
            assessment_criteria = json.dumps(assessment_criteria, ensure_ascii=False)
        
        # Run assessment
        result = assessor(
            task_instruction=task_instruction,
            assessment_criteria=assessment_criteria,
            solution_hints=solution_hints,
            student_answer=student_answer
        )
        
        # Parse score (ensure it's an integer between 1-5)
        try:
            score = int(result.score)
            if score < 1:
                score = 1
            elif score > 5:
                score = 5
        except (ValueError, TypeError):
            print(f"WARNUNG: Ungültiger Score '{result.score}', verwende 1")
            score = 1
        
        reasoning = result.reasoning or "Keine Begründung verfügbar"
        
        print(f"✓ Mastery-Bewertung abgeschlossen: Score={score}")
        
        return {
            'score': score,
            'reasoning': reasoning
        }
        
    except Exception as e:
        print(f"FEHLER bei Mastery-Bewertung: {e}")
        traceback.print_exc()
        return {
            'score': 1,
            'reasoning': f'Fehler bei der Bewertung: {str(e)}'
        }