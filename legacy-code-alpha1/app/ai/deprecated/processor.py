# app/ai/processor.py
"""
Orchestrierung der zweistufigen Feedback-Pipeline.
Implementiert die atomare Analyse pro Kriterium und die pädagogische Synthese.
"""

import json
import re
import dspy
import traceback
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Import der DSPy-Signaturen
from .signatures import AnalyseSingleCriterion, GeneratePedagogicalFeedback, AnalyzeSubmission

def parse_template_response(response: str) -> Dict[str, Optional[str]]:
    """
    DEPRECATED: Wird nur noch von der atomaren Analyse verwendet.
    Behalten für mögliche spätere Nutzung.
    
    Parst die Template-formatierte Antwort des LLMs.
    
    Erwartet Format:
    STATUS: erfüllt/nicht erfüllt/teilweise erfüllt
    ZITAT: "Das wörtliche Zitat"
    ANALYSE: Die Begründung
    
    Returns:
        Dict mit keys: status, quote, analysis (oder None wenn nicht gefunden)
    """
    result = {
        'status': None,
        'quote': None,
        'analysis': None
    }
    
    if not response:
        return result
    
    # Status extrahieren (case-insensitive)
    status_patterns = [
        r'STATUS:\s*(erfüllt|nicht erfüllt|teilweise erfüllt)',
        r'Status:\s*(erfüllt|nicht erfüllt|teilweise erfüllt)',
        r'status:\s*(erfüllt|nicht erfüllt|teilweise erfüllt)'
    ]
    
    for pattern in status_patterns:
        status_match = re.search(pattern, response, re.IGNORECASE)
        if status_match:
            result['status'] = status_match.group(1).lower()
            break
    
    # Zitat extrahieren (mit oder ohne Anführungszeichen)
    quote_patterns = [
        r'ZITAT:\s*"([^"]+)"',  # Mit Anführungszeichen
        r'ZITAT:\s*"([^"]+)"',  # Mit typografischen Anführungszeichen
        r'ZITAT:\s*\'([^\']+)\'',  # Mit einfachen Anführungszeichen
        r'ZITAT:\s*([^\n]+?)(?=\n(?:ANALYSE|STATUS)|$)'  # Ohne Anführungszeichen bis Zeilenende
    ]
    
    for pattern in quote_patterns:
        quote_match = re.search(pattern, response, re.IGNORECASE | re.DOTALL)
        if quote_match:
            result['quote'] = quote_match.group(1).strip()
            break
    
    # Analyse extrahieren (alles nach ANALYSE: bis zum Ende oder nächsten Label)
    analysis_patterns = [
        r'ANALYSE:\s*(.+?)(?=\n(?:STATUS|ZITAT):|$)',
        r'Analyse:\s*(.+?)(?=\n(?:Status|Zitat):|$)',
        r'analyse:\s*(.+?)(?=\n(?:status|zitat):|$)'
    ]
    
    for pattern in analysis_patterns:
        analysis_match = re.search(pattern, response, re.IGNORECASE | re.DOTALL)
        if analysis_match:
            result['analysis'] = analysis_match.group(1).strip()
            break
    
    # Fallback: Wenn Status nicht im erwarteten Format, versuche Schlüsselwörter
    if not result['status']:
        if 'erfüllt' in response.lower() and 'nicht erfüllt' not in response.lower():
            result['status'] = 'erfüllt'
        elif 'nicht erfüllt' in response.lower():
            result['status'] = 'nicht erfüllt'
        elif 'teilweise' in response.lower():
            result['status'] = 'teilweise erfüllt'
    
    return result

def process_submission_with_atomic_analysis(
    submission_id: str,
    task_details: Dict,
    submission_data: Dict,
    student_persona: str = "Schüler/in"  # TODO: Klassenstufe aus Profil holen
) -> Tuple[Optional[Dict], Optional[str]]:
    """
    DEPRECATED: Atomare Analyse - behalten für mögliche spätere Nutzung.
    Diese Funktion analysiert jedes Kriterium einzeln (N+1 LLM Calls).
    Wurde ersetzt durch analyze_submission() für bessere Effizienz.
    
    Führt die zweistufige Analyse durch:
    1. Atomare Analyse jedes Kriteriums
    2. Pädagogische Synthese zu Feed-Back und Feed-Forward
    
    Args:
        submission_id: ID der Einreichung
        task_details: Aufgabendetails inkl. assessment_criteria und solution_hints
        submission_data: Schülerlösung
        student_persona: Beschreibung des Schülers (z.B. "9. Klasse")
    
    Returns:
        Tuple von (Feedback-Dict, Error-String)
        Feedback-Dict enthält: feed_back_text, feed_forward_text, criteria_analysis
    """
    print(f"\n=== Starte atomare Feedback-Analyse für Submission {submission_id} ===")
    
    # Validierung der Eingaben
    if not task_details.get('assessment_criteria'):
        return None, "Keine Bewertungskriterien definiert"
    
    if not submission_data.get('text'):
        return None, "Keine Schülerlösung vorhanden"
    
    # Schritt 1: Atomare Analyse pro Kriterium
    atomic_analyzer = dspy.Predict(AnalyseSingleCriterion)
    final_analysis = {"strengths": [], "weaknesses": []}
    analyzed_count = 0
    
    criteria_list = task_details['assessment_criteria']
    print(f"Analysiere {len(criteria_list)} Kriterien...")
    
    for idx, criterion in enumerate(criteria_list):
        print(f"\n--- Kriterium {idx+1}/{len(criteria_list)}: {criterion} ---")
        
        try:
            # Atomare Analyse für dieses Kriterium
            result = atomic_analyzer(
                task_description=task_details['instruction'],
                student_solution=submission_data['text'],
                solution_hints=task_details.get('solution_hints', ''),
                criterion_to_check=criterion
            )
            
            # Parse die Template-Antwort
            if hasattr(result, 'single_analysis_text'):
                # Debug: Zeige die rohe Antwort
                print(f"   Raw LLM response: {result.single_analysis_text[:200]}...")
                
                # Parse das Template-Format
                analysis_data = parse_template_response(result.single_analysis_text)
                analysis_data['criterion'] = criterion  # Kriterium hinzufügen für Kontext
                
                # Validiere dass wir mindestens einen Status haben
                if analysis_data.get('status'):
                    # Sortiere in strengths oder weaknesses
                    if analysis_data.get('status') == 'erfüllt':
                        final_analysis["strengths"].append(analysis_data)
                        print(f"   ✓ Kriterium erfüllt")
                    else:
                        final_analysis["weaknesses"].append(analysis_data)
                        print(f"   ✗ Kriterium {analysis_data.get('status', 'nicht erfüllt')}")
                    
                    analyzed_count += 1
                else:
                    print(f"   ! Konnte Status nicht aus Antwort extrahieren")
                    print(f"   ! Parsed data: {analysis_data}")
            else:
                print(f"   ! Keine gültige Analyse erhalten (kein single_analysis_text Feld)")
                
        except Exception as e:
            print(f"   ! Fehler bei der Analyse: {e}")
            print(f"   ! Type of error: {type(e).__name__}")
            print(traceback.format_exc())
            continue
    
    # Prüfe ob mindestens ein Kriterium analysiert wurde
    if analyzed_count == 0:
        return None, "Keine Kriterien konnten erfolgreich analysiert werden"
    
    print(f"\nAnalyse abgeschlossen: {len(final_analysis['strengths'])} Stärken, {len(final_analysis['weaknesses'])} Schwächen")
    
    # Schritt 2: Pädagogische Synthese
    if not (final_analysis["strengths"] or final_analysis["weaknesses"]):
        return None, "Keine Analyseergebnisse für Synthese vorhanden"
    
    print("\n=== Starte pädagogische Feedback-Synthese ===")
    feedback_synthesizer = dspy.Predict(GeneratePedagogicalFeedback)
    
    try:
        # TODO: feedback_history für Mehrfachabgaben später implementieren
        final_feedback = feedback_synthesizer(
            analysis_input=json.dumps(final_analysis, ensure_ascii=False),  # Neuer Parameter-Name
            student_solution=submission_data['text'],  # NEU: Schülerlösung mitgeben
            feedback_history=None  # Vorerst keine Historie
        )
        
        # Extrahiere die Feedback-Teile
        if hasattr(final_feedback, 'feed_back_text') and hasattr(final_feedback, 'feed_forward_text'):
            feedback_result = {
                'feed_back_text': final_feedback.feed_back_text.strip(),
                'feed_forward_text': final_feedback.feed_forward_text.strip(),
                'criteria_analysis': json.dumps(final_analysis, ensure_ascii=False),
                'generated_at': datetime.now().isoformat()
            }
            
            print(f"✓ Feedback erfolgreich generiert")
            print(f"  Feed-Back Länge: {len(feedback_result['feed_back_text'])} Zeichen")
            print(f"  Feed-Forward Länge: {len(feedback_result['feed_forward_text'])} Zeichen")
            
            return feedback_result, None
        else:
            return None, "Feedback-Synthese hat keine gültigen Ausgabefelder erzeugt"
            
    except Exception as e:
        print(f"! Fehler bei der Feedback-Synthese: {e}")
        print(traceback.format_exc())
        return None, f"Fehler bei der Feedback-Synthese: {str(e)}"


def analyze_submission(
    submission_id: str,
    task_details: Dict,
    submission_data: Dict
) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Analysiert die Schülerlösung mit allen Kriterien in einem LLM-Call.
    Ersetzt die atomare Analyse für bessere Effizienz.
    
    Args:
        submission_id: ID der Einreichung
        task_details: Aufgabendetails inkl. assessment_criteria und solution_hints
        submission_data: Schülerlösung
    
    Returns:
        Tuple von (Feedback-Dict, Error-String)
        Feedback-Dict enthält: feed_back_text, feed_forward_text, criteria_analysis
    """
    print(f"\n=== Starte holistische Feedback-Analyse für Submission {submission_id} ===")
    
    # Validierung der Eingaben
    if not task_details.get('assessment_criteria'):
        return None, "Keine Bewertungskriterien definiert"
    
    if not submission_data.get('text'):
        return None, "Keine Schülerlösung vorhanden"
    
    try:
        # Schritt 1: Analyse aller Kriterien in einem Call
        analyzer = dspy.Predict(AnalyzeSubmission)
        
        # Kriterien als String formatieren
        criteria_text = "\n".join([f"- {c}" for c in task_details['assessment_criteria']])
        print(f"Analysiere {len(task_details['assessment_criteria'])} Kriterien in einem Call...")
        
        result = analyzer(
            task_description=task_details['instruction'],
            student_solution=submission_data['text'],
            solution_hints=task_details.get('solution_hints', ''),
            criteria_list=criteria_text
        )
        
        if not hasattr(result, 'analysis_text'):
            return None, "Keine Analyse vom LLM erhalten"
        
        print(f"✓ Analyse abgeschlossen (Länge: {len(result.analysis_text)} Zeichen)")
        
        # Schritt 2: Pädagogische Synthese
        print("\n=== Starte pädagogische Feedback-Synthese ===")
        feedback_synthesizer = dspy.Predict(GeneratePedagogicalFeedback)
        
        final_feedback = feedback_synthesizer(
            analysis_input=result.analysis_text,
            student_solution=submission_data['text'],
            feedback_history=None
        )
        
        # Extrahiere die Feedback-Teile
        if hasattr(final_feedback, 'feed_back_text') and hasattr(final_feedback, 'feed_forward_text'):
            feedback_result = {
                'feed_back_text': final_feedback.feed_back_text.strip(),
                'feed_forward_text': final_feedback.feed_forward_text.strip(),
                'criteria_analysis': json.dumps({
                    "analysis_text": result.analysis_text,
                    "method": "holistic"
                }, ensure_ascii=False),
                'generated_at': datetime.now().isoformat()
            }
            
            print(f"✓ Feedback erfolgreich generiert")
            print(f"  Feed-Back Länge: {len(feedback_result['feed_back_text'])} Zeichen")
            print(f"  Feed-Forward Länge: {len(feedback_result['feed_forward_text'])} Zeichen")
            
            return feedback_result, None
        else:
            return None, "Feedback-Synthese hat keine gültigen Ausgabefelder erzeugt"
            
    except Exception as e:
        print(f"! Fehler bei der holistischen Analyse: {e}")
        print(traceback.format_exc())
        return None, f"Fehler bei der holistischen Analyse: {str(e)}"