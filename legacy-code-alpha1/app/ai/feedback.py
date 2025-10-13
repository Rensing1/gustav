"""KI-Feedback-Generierung für Schülerantworten."""
# feedback.py
import sys
import os
import json
import dspy
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

# Füge das übergeordnete Verzeichnis (app) zum Python-Pfad hinzu
current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.dirname(current_dir)
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from ai.config import ensure_lm_configured
from ai.mastery import MasteryScorer
from ai.timeout_wrapper import with_timeout, TimeoutException
from utils.db_queries import (
    get_task_details,
    update_submission_ai_results,
    get_submission_by_id,
    get_submission_history
)


# ========== SIGNATUREN ==========

class AnalyzeSubmission(dspy.Signature):
    """
    Du bist Gymnasiallehrer und formulierst eine objektive Diagnose zu einer abgegebenen Schülerlösung.
    Deine Analyse ist kriterienspezifisch, evidenzbasiert und konsistent aufgebaut.
    """

    task_description = dspy.InputField(desc="Die genaue Aufgabenstellung.")
    student_solution = dspy.InputField(desc="Die Original-Schülerlösung.")
    solution_hints = dspy.InputField(desc="Lösungshinweise oder Musterlösung.")
    criteria_list = dspy.InputField(desc="Geordnete Liste der zu prüfenden Kriterien.")

    analysis_text = dspy.OutputField(
        desc="""Analysiere JEDES Kriterium in der vorgegebenen Reihenfolge mit folgender Struktur:

**Kriterium: [Name des Kriteriums]**
Status: [erfüllt / überwiegend erfüllt / teilweise erfüllt / nicht erfüllt]
Beleg: "[Wörtliches Zitat aus der Schülerlösung ODER 'Kein relevanter Beleg gefunden.']"
Analyse: [Kurze, objektive Begründung der Bewertung, OHNE Vermutungen]

REGELN:
- Beziehe dich ausschließlich auf die Schülerlösung, nicht auf Annahmen über die Person.
- Falls kein relevanter Textausschnitt vorhanden ist, schreibe explizit 'Kein relevanter Beleg gefunden'.
- Jede Analyse muss klar begründen, WARUM die Bewertung so ausfällt.
- Verwende nur neutrale, sachliche Formulierungen.
"""
    )


class GeneratePedagogicalFeedback(dspy.Signature):
    """
    Du bist Gymnasiallehrer und formulierst auf Basis einer Analyse ein pädagogisch wertvolles, motivierendes Feedback.
    Dein Ziel ist, den Lernfortschritt zu fördern, ohne die Lösung direkt vorzugeben.
    Falls vorhanden, berücksichtigst du dabei auch den direkt vorherigen Lösungsversuch, um die Entwicklung aufzuzeigen.
    Orientiere dich dabei stets an der Musterlösung als Zielvorgabe.
    """

    analysis_input = dspy.InputField(desc="Analyse der Schülerlösung")
    student_solution = dspy.InputField(desc="Lösung des Schülers")
    submission_history = dspy.InputField(
        desc="vorheriger Lösungsversuch"
    )
    solution_hints = dspy.InputField(desc="Musterlösung oder Lösungshinweise")

    feed_back_text = dspy.OutputField(
        desc="""Formuliere den Feed-Back Teil („Wo stehe ich?“):

REGELN:
- Beginne IMMER mit einer spezifischen positiven Beobachtung.
- Wenn es eine Verbesserung zu einem früheren Versuch gibt, hebe diese explizit hervor (z.B. "Im Vergleich zum letzten Mal hast du dich bei... deutlich verbessert.").
- Beziehe dich auf eine konkrete Stelle in der Schülerlösung.
"""
    )

    feed_forward_text = dspy.OutputField(
        desc="""Formuliere den Feed-Forward Teil („Wo geht es hin?“):

REGELN:
- Gib EINEN konkreten, umsetzbaren Tipp ODER stelle EINE gezielte Frage, die zum Nachdenken anregt. Beziehe dich dabei auf die Lösungshinweise.
- Wenn es eine Verbesserung zu einem früheren Versuch gibt, kann der Tipp darauf aufbauen.
- KEINE direkte Lösung vorgeben.
"""
    )


# ========== MODULE ==========

class FeedbackModule(dspy.Module):
    """DSPy-Modul für zweistufige Feedback-Generierung."""

    def __init__(self):
        super().__init__()
        self.analyze = dspy.Predict(AnalyzeSubmission)
        self.synthesize = dspy.Predict(GeneratePedagogicalFeedback)

    def forward(self, task_details: Dict, submission_text: str, submission_history: str) -> Dict:
        """Führt die komplette Feedback-Pipeline aus."""

        # Schritt 1: Analyse
        criteria_text = "\n".join([f"- {c}" for c in task_details["assessment_criteria"]])

        analysis = self.analyze(
            task_description=task_details["instruction"],
            student_solution=submission_text,
            solution_hints=task_details.get("solution_hints", ""),
            criteria_list=criteria_text
        )

        # Schritt 2: Feedback-Synthese
        feedback = self.synthesize(
            analysis_input=analysis.analysis_text,
            student_solution=submission_text,
            submission_history=submission_history,
            solution_hints=task_details.get("solution_hints", "")
        )

        return {
            "feed_back_text": feedback.feed_back_text.strip(),
            "feed_forward_text": feedback.feed_forward_text.strip(),
            "analysis": analysis.analysis_text
        }


class CombinedMasteryFeedbackModule(dspy.Module):
    """
    Ein DSPy-Modul, das die quantitative Bewertung (MasteryScorer) mit der
    qualitativen pädagogischen Feedback-Generierung (FeedbackModule) kombiniert.
    """

    def __init__(self):
        super().__init__()
        self.mastery_scorer = MasteryScorer()
        self.feedback_generator = FeedbackModule()

    def forward(self, task_details: Dict, student_answer: str, submission_history: str) -> Dict:
        """
        Führt die kombinierte Bewertungs- und Feedback-Pipeline aus.

        Returns:
            Ein Dictionary mit 'q_vec', 'feed_back_text', 'feed_forward_text', 'analysis'.
        """
        # 1. Quantitative Bewertung für Spaced Repetition Algorithmus
        mastery_result = self.mastery_scorer(task_details, student_answer)

        # 2. Pädagogisches Feedback generieren
        pedagogical_feedback = self.feedback_generator(
            task_details=task_details,
            submission_text=student_answer,
            submission_history=submission_history
        )

        # 3. Ergebnisse kombinieren
        return {
            "q_vec": mastery_result["q_vec"],
            "feed_back_text": pedagogical_feedback["feed_back_text"],
            "feed_forward_text": pedagogical_feedback["feed_forward_text"],
            "analysis": pedagogical_feedback["analysis"]
        }


# ========== SERVICE FUNKTIONEN ==========

def generate_ai_insights_for_submission(submission_id: str):
    """Generiert und speichert KI-Feedback für eine Submission."""

    print(f"\n=== Generiere Feedback für Submission {submission_id} ===")

    # LM Check
    if not ensure_lm_configured():
        print("FEHLER: KI-System nicht verfügbar")
        update_submission_ai_results(
            submission_id=submission_id,
            feedback="Fehler: KI-System nicht verfügbar"
        )
        return

    # === Lade Submission und Task-Daten ===
    try:
        current_submission, error = get_submission_by_id(submission_id)
        if error or not current_submission:
            raise Exception(f"Konnte aktuelle Submission nicht laden: {error}")

        student_id = current_submission.get("student_id")
        task_id = current_submission.get("task_id")
        submission_data = current_submission.get("submission_data")
        current_attempt = current_submission.get("attempt_number")

        if not all([student_id, task_id, submission_data, current_attempt]):
            raise Exception(
                "Unvollständige Daten in der Submission (student_id, task_id, submission_data, attempt_number fehlen)."
            )

    except Exception as e:
        print(f"FEHLER: Kritische Daten konnten nicht geladen werden. Abbruch. Grund: {e}")
        update_submission_ai_results(
            submission_id=submission_id,
            feedback=f"Fehler: Kritische Daten konnten nicht geladen werden: {e}"
        )
        return
    # === Ende Datenladen ===

    # === Lade Historie (nur letzter Versuch) ===
    submission_history_str = "Kein vorheriger Versuch verfügbar."
    try:
        if current_attempt > 1:
            previous_attempt_num = current_attempt - 1
            history, error = get_submission_history(student_id, task_id)
            if error:
                raise Exception(f"Fehler beim Laden der Historie: {error}")

            previous_submission = next(
                (s for s in history if s.get("attempt_number") == previous_attempt_num),
                None
            )

            if previous_submission:
                solution_text = previous_submission.get("submission_data", {}).get("text", "(Kein Text)")
                submission_history_str = f"---\n{solution_text}\n---"
                print(f"INFO: Vorheriger Versuch {previous_attempt_num} wird berücksichtigt.")

    except Exception as e:
        print(f"WARNUNG: Konnte Submission-Historie nicht laden, fahre ohne fort. Grund: {e}")
    # === Ende Historie ===

    # Task laden
    task_details, error = get_task_details(task_id)
    if error:
        print(f"FEHLER: {error}")
        update_submission_ai_results(submission_id=submission_id, feedback=f"Fehler: {error}")
        return

    # Validierung
    if not task_details.get("assessment_criteria"):
        print("FEHLER: Keine Bewertungskriterien definiert")
        update_submission_ai_results(
            submission_id=submission_id,
            feedback="Fehler: Keine Bewertungskriterien definiert"
        )
        return

    if not submission_data.get("text"):
        print("FEHLER: Keine Schülerlösung vorhanden")
        update_submission_ai_results(
            submission_id=submission_id,
            feedback="Fehler: Keine Schülerlösung vorhanden"
        )
        return

    # Feedback generieren
    try:
        feedback_module = FeedbackModule()
        
        # Rufe Modul mit Timeout auf (120 Sekunden)
        @with_timeout(120)
        def generate_feedback():
            return feedback_module(
                task_details=task_details,
                submission_text=submission_data["text"],
                submission_history=submission_history_str
            )
        
        result = generate_feedback()

        # In DB speichern
        combined = f"{result['feed_back_text']}\n\n{result['feed_forward_text']}"

        success, error = update_submission_ai_results(
            submission_id=submission_id,
            criteria_analysis=json.dumps({
                "analysis_text": result["analysis"],
                "method": "holistic_v3_history_prev_only"
            }, ensure_ascii=False),
            feedback=combined,
            rating_suggestion=None,
            feed_back_text=result["feed_back_text"],
            feed_forward_text=result["feed_forward_text"]
        )

        if success:
            print("✓ Feedback erfolgreich generiert und gespeichert")
        else:
            print(f"! Fehler beim Speichern: {error}")

    except TimeoutException:
        print(f"TIMEOUT: KI-Feedback-Generierung dauerte zu lange (>120s)")
        update_submission_ai_results(
            submission_id=submission_id,
            feedback="Die Feedback-Generierung dauerte zu lange. Bitte versuche es später erneut."
        )
        raise  # Re-raise für Worker
        
    except Exception as e:
        print(f"FEHLER bei Feedback-Generierung: {e}")
        import traceback
        traceback.print_exc()

        update_submission_ai_results(
            submission_id=submission_id,
            feedback=f"Unerwarteter Fehler bei KI-Analyse: {str(e)}"
        )


# ========== TESTING ==========

def test_feedback():
    """Einfacher Test mit Ollama."""

    if not ensure_lm_configured():
        print("SKIP: Ollama nicht verfügbar")
        return False

    test_task = {
        "instruction": "Erkläre die Photosynthese in 3 Sätzen.",
        "assessment_criteria": [
            "Erwähnt Chlorophyll oder grüne Pflanzenteile",
            "Beschreibt Umwandlung von CO2 und Wasser",
            "Nennt Sonnenlicht als Energiequelle"
        ],
        "solution_hints": "Photosynthese ist der Prozess, bei dem Pflanzen Lichtenergie nutzen"
    }

    test_answer = "Pflanzen nehmen Sonnenlicht auf und machen daraus Energie."

    try:
        module = FeedbackModule()
        result = module(test_task, test_answer, "Kein vorheriger Versuch.")

        print("\n=== TEST ERGEBNIS ===")
        print(f"\nFeed-Back:\n{result['feed_back_text']}")
        print(f"\nFeed-Forward:\n{result['feed_forward_text']}")
        print("\n✓ Test erfolgreich")
        return True

    except Exception as e:
        print(f"\n✗ Test fehlgeschlagen: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Standalone test - nur die Module testen ohne DB
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print("\n=== Teste Feedback-Modul (ohne DB) ===")

    if not ensure_lm_configured():
        print("FEHLER: LM nicht konfiguriert")
        sys.exit(1)

    test_task = {
        "instruction": "Erkläre die Photosynthese in 3 Sätzen.",
        "assessment_criteria": [
            "Erwähnt Chlorophyll oder grüne Pflanzenteile",
            "Beschreibt Umwandlung von CO2 und Wasser",
            "Nennt Sonnenlicht als Energiequelle"
        ],
        "solution_hints": "Photosynthese ist der Prozess, bei dem Pflanzen Lichtenergie nutzen"
    }

    test_answer = "Pflanzen nehmen Sonnenlicht auf und machen daraus Energie."

    try:
        module = FeedbackModule()
        result = module(test_task, test_answer, "Kein vorheriger Versuch.")

        print("\n=== TEST ERGEBNIS ===")
        print(f"\nFeed-Back:\n{result['feed_back_text']}")
        print(f"\nFeed-Forward:\n{result['feed_forward_text']}")
        print("\n✓ Feedback-Modul funktioniert!")

    except Exception as e:
        print(f"\n✗ Test fehlgeschlagen: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

