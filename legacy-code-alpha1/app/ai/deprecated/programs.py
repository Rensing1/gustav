# app/ai/programs.py

import dspy
import traceback
from .signatures import (
    GenerateFocusedFeedback,  # Behalten für Kompatibilität
    AnalyseSingleCriterion, 
    GeneratePedagogicalFeedback,
    MasteryAssessment,
    ExtractTextFromImage
)
from typing import Optional
from dspy import LM as DSPYLM # Korrekter Import für Type Hint

class AtomicCriterionAnalyzer(dspy.Module):
    """
    DEPRECATED: Diese Klasse wird aktuell nicht genutzt.
    Behalten für mögliche Rückkehr zur atomaren Analyse.
    
    Analysiert die Schülerlösung bezüglich EINES spezifischen Kriteriums.
    Generiert strukturierte Antwort im Template-Format mit status, quote und analysis.
    """
    def __init__(self):
        super().__init__()
        # Verwende ChainOfThought für tiefere Analyse
        self.analyze = dspy.ChainOfThought(AnalyseSingleCriterion)
    
    def forward(self, task_description: str, student_solution: str, 
                solution_hints: str, criterion_to_check: str):
        """Führt die atomare Analyse für ein Kriterium durch."""
        # Zusätzliche Instruktionen und Beispiel für Template-Format
        template_instruction = """
WICHTIG: Antworte GENAU in diesem Format (mit Großbuchstaben für die Labels):

STATUS: erfüllt
ZITAT: "Hier steht das wörtliche Zitat aus der Schülerlösung"
ANALYSE: Hier steht die kurze, objektive Begründung warum das Kriterium erfüllt ist.

Beispiel für "nicht erfüllt":
STATUS: nicht erfüllt
ZITAT: "Der Schüler erwähnt nur oberflächlich..."
ANALYSE: Das Kriterium verlangt eine detaillierte Erklärung, aber der Text bleibt oberflächlich.

Benutze IMMER diese drei Labels: STATUS, ZITAT, ANALYSE."""
        
        return self.analyze(
            task_description=task_description,
            student_solution=student_solution,
            solution_hints=solution_hints,
            criterion_to_check=criterion_to_check + "\n\n" + template_instruction
        )

class PedagogicalFeedbackSynthesizer(dspy.Module):
    """
    DEPRECATED: Diese Klasse wird aktuell nicht genutzt.
    Behalten für mögliche Rückkehr zur atomaren Analyse.
    
    Synthetisiert aus der strukturierten Analyse ein pädagogisch wertvolles Feedback.
    Befolgt strenge pädagogische Regeln für konstruktives Feedback.
    """
    def __init__(self):
        super().__init__()
        # Verwende ChainOfThought für bessere Begründungen
        self.synthesize = dspy.ChainOfThought(GeneratePedagogicalFeedback)
        
        # Pädagogische Regeln als System-Prompt
        self.pedagogical_rules = """
Du bist GUSTAV, ein sachlicher und unterstützender Lern-Coach.

### Absolute Regeln:
1. **Spezifität:** Beziehe dich IMMER auf konkrete Zitate aus der Analyse.
2. **Keine Personenbewertung:** Bewerte NIEMALS die Person. Beziehe dich IMMER auf den Text.
3. **Keine Prozessbewertung:** Kommentiere NIEMALS den Lernprozess.
4. **Keine Lösungen:** Gib NIEMALS die Lösung direkt vor.

### Deine Aufgabe:
Basierend auf der folgenden Analyse, fülle die beiden Felder `feed_back_text` und `feed_forward_text` aus.

### FELD 1: `feed_back_text`
Beginne IMMER mit einer spezifischen, positiven Beobachtung. Beschreibe dann klar und wertfrei den wichtigsten Verbesserungspunkt.
Beispiel: "Super, ich sehe, du hast den Hinweis zur Einleitung umgesetzt! Sie ist jetzt viel prägnanter. Mir ist bei der Analyse deines Arguments aufgefallen, dass an der Stelle '...' noch ein Beleg fehlt, um es vollständig zu untermauern."

### FELD 2: `feed_forward_text`
Formuliere EINEN klaren, umsetzbaren Tipp oder stelle EINE gezielte Frage, die dem Schüler hilft, genau den im `feed_back_text` genannten Punkt zu verbessern. Schließe mit einer Ermutigung.
Beispiel: "Welche Textstelle könntest du zitieren, um deine Behauptung zu untermauern? Ich bin gespannt auf deine nächste Version!"
"""
    
    def forward(self, analysis_json: str, student_persona: str, 
                feedback_history: Optional[str] = None):
        """Generiert pädagogisches Feedback basierend auf der Analyse."""
        # Füge pädagogische Regeln zum Kontext hinzu
        enhanced_analysis = f"{self.pedagogical_rules}\n\n### Analyse:\n{analysis_json}"
        
        if feedback_history:
            enhanced_analysis += f"\n\n### Bisherige Feedback-Historie:\n{feedback_history}"
        
        return self.synthesize(
            analysis_json=enhanced_analysis,
            student_persona=student_persona,
            feedback_history=feedback_history
        )

# Behalte die alte Klasse vorerst für Kompatibilität
class GustavFeedbackGenerator(dspy.Module):
    """
    Ein DSPy-Modul, das fokussiertes Feedback generiert,
    indem es dspy.Predict mit der GenerateFocusedFeedback-Signatur verwendet.
    Der Prompt wird implizit durch die Signatur und den ChatAdapter von DSPy erstellt.
    """
    def __init__(self):
        super().__init__()
        # Initialisiere Predict NUR mit der Signatur.
        # DSPy wird versuchen, den Prompt basierend auf der Signatur und dem
        # konfigurierten LM (das Chat-fähig sein sollte) zu erstellen.
        self.generate_feedback = dspy.Predict(GenerateFocusedFeedback)

    def forward(self, task_instruction: str, student_solution: str, feedback_focus: str | None = None, lm: Optional[DSPYLM] = None):
        """
        Führt die Feedback-Generierung aus.

        Args:
            task_instruction: Die Aufgabenstellung.
            student_solution: Die Lösung des Schülers.
            feedback_focus: Optionaler Fokus vom Lehrer.
            lm: Die zu verwendende LM-Instanz (wird per dspy.context gesetzt).

        Returns:
            Ein dspy.Prediction-Objekt mit dem Feld 'feedback_text'.
        """
        # Das LM wird jetzt über dspy.context(lm=lm) im Service gesetzt,
        # daher hier keine explizite Übergabe an self.generate_feedback mehr nötig.
        # if lm is None:
        #     raise ValueError("Keine LM-Instanz an GustavFeedbackGenerator.forward übergeben!")

        effective_feedback_focus = feedback_focus if feedback_focus and feedback_focus.strip() else "Kein spezifischer Fokus vom Lehrer angegeben. Gib allgemeines, konstruktives Feedback."
        prediction = None

        # Der with dspy.context(lm=lm) Block ist jetzt in service.py
        try:
            print(">>> Programm: Starte Feedback-Generierung (Predict mit Signatur, Chat-Adapter erwartet)...")
            prediction = self.generate_feedback(
                task_instruction=task_instruction,
                student_solution=student_solution,
                feedback_focus=effective_feedback_focus
            )
            print("<<< Programm: Feedback-Generierung beendet.")
            if prediction and hasattr(prediction, 'feedback_text'):
                print(f"    Roh-Feedback-Output vom Predict-Modul: {prediction.feedback_text[:200]}...")
            else:
                print("    WARNUNG: Kein feedback_text im Prediction-Objekt gefunden oder Prediction ist None.")
                if prediction: print(f"    Prediction-Objekt: {prediction}")


        except Exception as e:
             print(f"!!! Programm: FEHLER während dspy.Predict(GenerateFocusedFeedback) !!!")
             print(traceback.format_exc())
             # prediction bleibt None oder enthält vorherigen Wert

        return prediction


class MasteryAssessor(dspy.Module):
    """
    Bewertet eine Schülerantwort auf einer Skala von 1-5 für Mastery Learning.
    Nutzt Chain-of-Thought für eine strukturierte Bewertung.
    """
    def __init__(self):
        super().__init__()
        # ChainOfThought für strukturierte Bewertung
        self.assess = dspy.ChainOfThought(MasteryAssessment)
    
    def forward(self, task_instruction: str, assessment_criteria: str, 
                solution_hints: str, student_answer: str):
        """
        Führt die Mastery-Bewertung durch.
        
        Args:
            task_instruction: Die Aufgabenstellung
            assessment_criteria: Bewertungskriterien als JSON-String
            solution_hints: Optionale Lösungshinweise
            student_answer: Die zu bewertende Schülerantwort
            
        Returns:
            dspy.Prediction mit 'score' und 'reasoning'
        """
        try:
            # Führe Bewertung durch
            result = self.assess(
                task_instruction=task_instruction,
                assessment_criteria=assessment_criteria,
                solution_hints=solution_hints or "",
                student_answer=student_answer
            )
            
            # Debug output
            if hasattr(result, 'score'):
                print(f"    Mastery Score: {result.score}")
                print(f"    Reasoning: {result.reasoning[:100]}...")
            
            return result
            
        except Exception as e:
            print(f"!!! FEHLER bei Mastery-Bewertung: {e}")
            traceback.print_exc()
            # Return a default low score on error
            class ErrorResult:
                score = "1"
                reasoning = f"Fehler bei der Bewertung: {str(e)}"
            return ErrorResult()

class VisionTextExtractor(dspy.Module):
    """
    DSPy-Module für Handschrifterkennung aus Bildern.
    Unterstützt konfigurierbares Model für Multi-Model-Setup.
    """
    def __init__(self, model_name: str = "gemma3:12b"):
        super().__init__()
        self.model_name = model_name
        # Predict für Vision-Tasks
        self.extract = dspy.Predict(ExtractTextFromImage)
    
    def forward(self, image_bytes: bytes):
        """
        Extrahiert Text aus Bild-Bytes mit DSPy 3.x dspy.Image.
        
        Args:
            image_bytes: Raw Bytes des Bildes
            
        Returns:
            dspy.Prediction mit 'extracted_text'
        """
        try:
            # DSPy 3.x: Erstelle dspy.Image aus Base64 Data URL (korrekte API)
            import base64
            print(f"[DSPy-Vision-DEBUG] Creating dspy.Image from {len(image_bytes)} bytes")
            b64_data = base64.b64encode(image_bytes).decode()
            data_url = f"data:image/png;base64,{b64_data}"
            image = dspy.Image(url=data_url)
            
            print(f"[DSPy-Vision-DEBUG] Calling extract with dspy.Image")
            result = self.extract(image=image)
            
            # DEBUG: Log the full response
            print(f"[DSPy-Vision-DEBUG] Full result object: {result}")
            print(f"[DSPy-Vision-DEBUG] Result attributes: {dir(result) if hasattr(result, '__dict__') else 'No __dict__'}")
            
            if hasattr(result, 'extracted_text'):
                print(f"[DSPy-Vision] Model: {self.model_name}, Extracted: {len(result.extracted_text)} chars")
                print(f"[DSPy-Vision-DEBUG] Extracted text content: '{result.extracted_text}'")
                return result
            else:
                print(f"[DSPy-Vision] Keine extracted_text in Response: {result}")
                # Fallback-Antwort
                class FallbackResult:
                    extracted_text = "[KEIN TEXT ERKENNBAR]"
                return FallbackResult()
                
        except Exception as e:
            print(f"[DSPy-Vision] Fehler bei {self.model_name}: {e}")
            traceback.print_exc()
            # Error-Antwort
            class ErrorResult:
                extracted_text = f"[Fehler bei der Verarbeitung: {str(e)}]"
            return ErrorResult()