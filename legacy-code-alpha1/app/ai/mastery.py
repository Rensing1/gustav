"""Wissensfestiger Assessment using dspy."""

import json
import dspy
import traceback
from typing import Dict

from .config import ensure_lm_configured

# ========== SIGNATURE =========="""

class MasteryAssessment(dspy.Signature):
    """
    Bewerte die Schülerantwort präzise anhand von drei Kriterien:
    Korrektheit, Vollständigkeit und Prägnanz.
    Gib für jedes Kriterium eine Fließkommazahl zwischen 0.0 und 1.0 zurück.
    Gib zusätzlich eine kurze Begründung für die Bewertung.
    
    Bewertungsskala (0.0 bis 1.0):
    - 1.0: Exzellent, vollständig und präzise.
    - 0.9: Sehr gut, fast perfekt.
    - 0.7: Gut, die Kernidee ist richtig, aber es gibt Lücken.
    - 0.5: Ausreichend, grundlegendes Verständnis erkennbar, aber wichtige Aspekte fehlen.
    - 0.3: Mangelhaft, Ansatzweise richtig, aber größere Fehler.
    - 0.0: Komplett falsch oder keine Antwort.
    
    Sei streng aber fair. Eine 1.0 sollte nur für wirklich exzellente Antworten vergeben werden.
    """
    
    task_instruction = dspy.InputField(desc="Die Aufgabenstellung, die der Schüler bearbeiten soll.")
    assessment_criteria = dspy.InputField(desc="Bewertungskriterien als JSON-Array mit den wichtigsten zu prüfenden Punkten.")
    solution_hints = dspy.InputField(desc="Optionale Lösungshinweise oder Musterlösung zur Orientierung.", optional=True)
    student_answer = dspy.InputField(desc="Die Antwort des Schülers, die bewertet werden soll.")
    
    korrektheit = dspy.OutputField(desc="Numerische Bewertung der inhaltlichen Korrektheit (0.0-1.0). Nur die Zahl.")
    vollstaendigkeit = dspy.OutputField(desc="Numerische Bewertung der Vollständigkeit (0.0-1.0). Nur die Zahl.")
    praegnanz = dspy.OutputField(desc="Numerische Bewertung der Prägnanz und Klarheit (0.0-1.0). Nur die Zahl.")
    reasoning = dspy.OutputField(desc="Kurze Begründung der Bewertung in 2-3 Sätzen. Erkläre, was gut war und was gefehlt hat.")


# ========== MODULE =========="""

class MasteryScorer(dspy.Module):
    """DSPy-Modul für die Bewertung des Wissensfestigers."""
    
    def __init__(self):
        super().__init__()
        self.assess = dspy.ChainOfThought(MasteryAssessment)
    
    def forward(self, task_details: Dict, student_answer: str) -> Dict:
        """
        Führt die Bewertung durch.
        
        Args:
            task_details: Dictionary mit instruction, assessment_criteria, solution_hints.
            student_answer: Die zu bewertende Schülerantwort.
            
        Returns:
            Dictionary mit 'q_vec' (Dict) und 'reasoning' (str).
        """
        
        task_instruction = task_details.get('instruction', '')
        assessment_criteria = task_details.get('assessment_criteria', [])
        solution_hints = task_details.get('solution_hints', '')
        
        criteria_json = json.dumps(assessment_criteria, ensure_ascii=False) if isinstance(assessment_criteria, list) else str(assessment_criteria)
        
        result = self.assess(
            task_instruction=task_instruction,
            assessment_criteria=criteria_json,
            solution_hints=solution_hints or "",
            student_answer=student_answer
        )
        
        def _parse_float(value_str: str, default: float = 0.0) -> float:
            try:
                # Handle comma as decimal separator
                val = float(value_str.strip().replace(',', '.'))
                return max(0.0, min(1.0, val))  # Clamp to 0.0-1.0
            except (ValueError, TypeError, AttributeError):
                print(f"WARNUNG: Ungültiger Float-Wert '{value_str}', verwende {default}")
                return default

        q_vec = {
            'korrektheit': _parse_float(result.korrektheit),
            'vollstaendigkeit': _parse_float(result.vollstaendigkeit),
            'praegnanz': _parse_float(result.praegnanz)
        }
        
        reasoning = result.reasoning if hasattr(result, 'reasoning') else "Keine Begründung verfügbar."
        
        print(f"    Wissensfestiger q_vec: {q_vec}")
        print(f"    Reasoning: {reasoning[:100]}...")
        
        return {
            'q_vec': q_vec,
            'reasoning': reasoning
        }


# ========== SERVICE FUNCTION =========="""

def generate_mastery_assessment(task_details: dict, student_answer: str) -> dict:
    """
    Generiert eine differenzierte Bewertung für eine Wissensfestiger-Aufgabe.
    
    Args:
        task_details: Dictionary mit task_instruction, assessment_criteria, solution_hints.
        student_answer: Die Antwort des Schülers.
        
    Returns:
        Dictionary mit 'q_vec' und 'reasoning'.
    """
    
    print("\n--- Starte Wissensfestiger-Bewertung ---")
    
    if not ensure_lm_configured():
        print("FEHLER: Globales LM nicht konfiguriert.")
        return {
            'q_vec': {'korrektheit': 0.0, 'vollstaendigkeit': 0.0, 'praegnanz': 0.0},
            'reasoning': 'KI-System nicht verfügbar'
        }
    
    try:
        scorer = MasteryScorer()
        result = scorer(task_details, student_answer)
        print(f"✓ Wissensfestiger-Bewertung abgeschlossen: q_vec={result['q_vec']}")
        return result
        
    except Exception as e:
        print(f"FEHLER bei Wissensfestiger-Bewertung: {e}")
        traceback.print_exc()
        return {
            'q_vec': {'korrektheit': 0.0, 'vollstaendigkeit': 0.0, 'praegnanz': 0.0},
            'reasoning': f'Fehler bei der Bewertung: {str(e)}'
        }

# ========== TESTING =========="""

def test_mastery():
    """Einfacher Test mit Ollama."""
    
    if not ensure_lm_configured():
        print("SKIP: Ollama nicht verfügbar")
        return False
    
    test_task = {
        'instruction': 'Was ist der Unterschied zwischen Mitose und Meiose?',
        'assessment_criteria': [
            'Nennt Anzahl der Tochterzellen',
            'Erwähnt Chromosomenzahl in Tochterzellen (diploid/haploid)',
            'Beschreibt Zweck/Funktion beider Prozesse (Körperzellen vs. Keimzellen)'
        ],
        'solution_hints': 'Mitose: 2 diploide Tochterzellen für Wachstum. Meiose: 4 haploide Keimzellen für Fortpflanzung.'
    }
    
    test_answer = "Mitose macht zwei Zellen und Meiose macht vier Zellen. Es ist für die Vermehrung."
    
    try:
        result = generate_mastery_assessment(test_task, test_answer)
        
        print("\n=== TEST ERGEBNIS ===")
        print(f"Q-Vektor: {result['q_vec']}")
        print(f"Begründung: {result['reasoning']}")
        
        # Validate result
        assert isinstance(result['q_vec'], dict)
        assert 'korrektheit' in result['q_vec']
        assert 0.0 <= result['q_vec']['korrektheit'] <= 1.0
        assert isinstance(result['reasoning'], str)
        
        print("\n✓ Test erfolgreich")
        return True
        
    except Exception as e:
        print(f"\n✗ Test fehlgeschlagen: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Standalone test
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    print("\n=== Teste Wissensfestiger-Modul ===")
    
    if not ensure_lm_configured():
        print("FEHLER: LM nicht konfiguriert")
        sys.exit(1)
    
    test_mastery()
