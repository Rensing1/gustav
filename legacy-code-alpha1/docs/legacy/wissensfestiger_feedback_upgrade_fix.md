# Implementierungsplan: Pädagogisches Feedback im Wissensfestiger (Fehlerkorrektur)

Hier ist der korrigierte und vollständige Plan, um das `reasoning`-basierte Feedback im Wissensfestiger-Modul durch das zweistufige, pädagogische Feedback (Feed-Back/Feed-Forward) zu ersetzen. Der Fehler, der dazu führte, dass keine Mastery-Aufgaben mehr gefunden wurden, ist in diesem Plan behoben.

## Schritt 1: `app/ai/feedback.py` aktualisieren

Ersetze den gesamten Inhalt der Datei `app/ai/feedback.py` mit dem folgenden Code. 

**Änderungen:**
- **Importiert `MasteryScorer`** aus `ai.mastery`.
- **Fügt das neue `CombinedMasteryFeedbackModule` hinzu**, das `MasteryScorer` und `FeedbackModule` kombiniert, um sowohl die quantitativen Scores (`q_vec`) als auch das qualitative Feedback in einem Durchgang zu erzeugen.

```python
"""KI-Feedback-Generierung für Schülerantworten."""

import sys
import os
import json
import dspy
from datetime import datetime
from typing import Dict, Optional, Tuple

# Füge das übergeordnete Verzeichnis (app) zum Python-Pfad hinzu
current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.dirname(current_dir)
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from ai.config import ensure_lm_configured
from ai.mastery import MasteryScorer
from utils.db_queries import get_task_details, update_submission_ai_results, get_submission_by_id, get_submission_history


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
        desc='''Analysiere JEDES Kriterium in der vorgegebenen Reihenfolge mit folgender Struktur:

**Kriterium: [Name des Kriteriums]**
Status: [erfüllt / überwiegend erfüllt / teilweise erfüllt / nicht erfüllt]
Beleg: "[Wörtliches Zitat aus der Schülerlösung ODER 'Kein relevanter Beleg gefunden.']"
Analyse: [Kurze, objektive Begründung der Bewertung, OHNE Vermutungen]

REGELN:
- Beziehe dich ausschließlich auf die Schülerlösung, nicht auf Annahmen über die Person.
- Falls kein relevanter Textausschnitt vorhanden ist, schreibe explizit 'Kein relevanter Beleg gefunden'.
- Jede Analyse muss klar begründen, WARUM die Bewertung so ausfällt.
- Verwende nur neutrale, sachliche Formulierungen.
'''
    )


class GeneratePedagogicalFeedback(dspy.Signature):
    """
    Du bist Gymnasiallehrer und formulierst auf Basis einer Analyse ein pädagogisch wertvolles, motivierendes Feedback.
    Dein Ziel ist, den Lernfortschritt zu fördern, ohne die Lösung direkt vorzugeben.
    Du berücksichtigst dabei auch den direkt vorherigen Lösungsversuch, um die Entwicklung aufzuzeigen.
    """
    
    analysis_input = dspy.InputField(desc="Die vollständige Analyse der aktuellen Schülerlösung.")
    student_solution = dspy.InputField(desc="Die aktuelle Original-Schülerlösung.")
    submission_history = dspy.InputField(desc="Die Lösung des direkt vorherigen Versuchs. Kann leer sein, wenn dies der erste Versuch ist.")
    
    feed_back_text = dspy.OutputField(
        desc='''Formuliere den Feed-Back Teil („Wo stehe ich?“):

REGELN:
- Beginne IMMER mit einer spezifischen positiven Beobachtung.
- Wenn es eine Verbesserung zu einem früheren Versuch gibt, hebe diese explizit hervor (z.B. "Im Vergleich zum letzten Mal hast du dich bei... deutlich verbessert.").
- Nenne anschließend GENAU EINEN klar priorisierten Verbesserungspunkt aus der Analyse.
- Beziehe dich auf eine konkrete Stelle in der Schülerlösung.
- Formuliere wertschätzend und freundlich.
'''
    )
    
    feed_forward_text = dspy.OutputField(
        desc='''Formuliere den Feed-Forward Teil („Wo geht es hin?“):

REGELN:
- Gib EINEN konkreten, umsetzbaren Tipp ODER stelle EINE gezielte Frage, die zum Nachdenken anregt.
- Wenn es eine Verbesserung zu einem früheren Versuch gibt, kann der Tipp darauf aufbauen.
- KEINE direkte Lösung vorgeben.
- Schließe mit einer motivierenden Standardformel wie "Ich bin gespannt auf deine nächste Version!"
'''
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
        criteria_text = "\n".join([
            f"- {c}" for c in task_details['assessment_criteria']
        ])
        
        analysis = self.analyze(
            task_description=task_details['instruction'],
            student_solution=submission_text,
            solution_hints=task_details.get('solution_hints', ''),
            criteria_list=criteria_text
        )
        
        # Schritt 2: Feedback-Synthese
        feedback = self.synthesize(
            analysis_input=analysis.analysis_text,
            student_solution=submission_text,
            submission_history=submission_history
        )
        
        return {
            'feed_back_text': feedback.feed_back_text.strip(),
            'feed_forward_text': feedback.feed_forward_text.strip(),
            'analysis': analysis.analysis_text
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
            'q_vec': mastery_result['q_vec'],
            'feed_back_text': pedagogical_feedback['feed_back_text'],
            'feed_forward_text': pedagogical_feedback['feed_forward_text'],
            'analysis': pedagogical_feedback['analysis']
        }


# ========== SERVICE FUNKTIONEN ========== 

def generate_ai_insights_for_submission(submission_id: str):
    """Generiert und speichert KI-Feedback für eine Submission."""
    
    print(f"\n=== Generiere Feedback für Submission {submission_id} ===")
    
    # LM Check
    if not ensure_lm_configured():
        print("FEHLER: KI-System nicht verfügbar")
        update_submission_ai_results(submission_id=submission_id, feedback="Fehler: KI-System nicht verfügbar")
        return

    # === Lade Submission und Task-Daten ===
    try:
        current_submission, error = get_submission_by_id(submission_id)
        if error or not current_submission:
            raise Exception(f"Konnte aktuelle Submission nicht laden: {error}")
        
        student_id = current_submission.get('student_id')
        task_id = current_submission.get('task_id')
        submission_data = current_submission.get('solution_data')
        current_attempt = current_submission.get('attempt_number')

        if not all([student_id, task_id, submission_data, current_attempt]):
            raise Exception("Unvollständige Daten in der Submission (student_id, task_id, solution_data, attempt_number fehlen).")

    except Exception as e:
        print(f"FEHLER: Kritische Daten konnten nicht geladen werden. Abbruch. Grund: {e}")
        update_submission_ai_results(submission_id=submission_id, feedback=f"Fehler: Kritische Daten konnten nicht geladen werden: {e}")
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
            
            previous_submission = next((s for s in history if s.get('attempt_number') == previous_attempt_num), None)

            if previous_submission:
                solution_text = previous_submission.get('solution_data', {}).get('text', '(Kein Text)')
                submission_history_str = f"--- LÖSUNG VON VERSUCH {previous_attempt_num} ---\n{solution_text}\n---"
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
    if not task_details.get('assessment_criteria'):
        print("FEHLER: Keine Bewertungskriterien definiert")
        update_submission_ai_results(submission_id=submission_id, feedback="Fehler: Keine Bewertungskriterien definiert")
        return
    
    if not submission_data.get('text'):
        print("FEHLER: Keine Schülerlösung vorhanden")
        update_submission_ai_results(submission_id=submission_id, feedback="Fehler: Keine Schülerlösung vorhanden")
        return
    
    # Feedback generieren
    try:
        feedback_module = FeedbackModule()
        result = feedback_module(
            task_details=task_details,
            submission_text=submission_data['text'],
            submission_history=submission_history_str
        )
        
        # In DB speichern
        combined = f"{result['feed_back_text']}\n\n{result['feed_forward_text']}"
        
        success, error = update_submission_ai_results(
            submission_id=submission_id,
            criteria_analysis=json.dumps({
                "analysis_text": result['analysis'],
                "method": "holistic_v3_history_prev_only"
            }, ensure_ascii=False),
            feedback=combined,  # Für Abwärtskompatibilität
            rating_suggestion=None,
            feed_back_text=result['feed_back_text'],
            feed_forward_text=result['feed_forward_text']
        )
        
        if success:
            print("✓ Feedback erfolgreich generiert und gespeichert")
        else:
            print(f"! Fehler beim Speichern: {error}")
        
    except Exception as e:
        print(f"FEHLER bei Feedback-Generierung: {e}")
        import traceback
        traceback.print_exc()
        
        update_submission_ai_results(submission_id=submission_id, feedback=f"Unerwarteter Fehler bei KI-Analyse: {str(e)}")

```

---

## Schritt 2: `app/utils/db_queries.py` aktualisieren (KORRIGIERT)

Ersetze den gesamten Inhalt der Datei `app/utils/db_queries.py` mit dem folgenden Code.

**Änderungen:**
- **Korrektur in `get_mastery_tasks_for_course`**: Die Abfrage filtert jetzt korrekt nach `course_id` (statt `unit_id`), um die dem Kurs zugewiesenen Lerneinheiten zu finden. **Dies behebt den gemeldeten Fehler.**
- **Importiert `CombinedMasteryFeedbackModule`** statt `generate_mastery_assessment`.
- **Überarbeitet `submit_mastery_answer` komplett:**
    - Holt jetzt die Submission-Historie.
    - Ruft das neue `CombinedMasteryFeedbackModule` auf.
    - Speichert das vollständige Ergebnis (Scores und pädagogisches Feedback) in der `submission`-Tabelle mit dem Service-Role-Key.
    - Ruft `_update_mastery_progress` auf, um die Lernfortschrittsdaten zu aktualisieren.
- **Entfernt die nicht mehr benötigte Funktion `save_mastery_submission`**.
- **Passt `_update_mastery_progress` an**, um den `service_client` als Parameter zu akzeptieren und so RLS-Probleme zu vermeiden.

```python
# app/utils/db_queries.py

import sys
import os
import json
import traceback
import random
from datetime import datetime, timezone, date
from typing import Dict, List, Optional, Tuple

# Füge das übergeordnete Verzeichnis (app) zum Python-Pfad hinzu
current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.dirname(current_dir)
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from supabase_client import supabase_client, get_supabase_service_client
from supabase import PostgrestAPIResponse
import streamlit as st

from ai.feedback import CombinedMasteryFeedbackModule
from mastery.mastery_config import INITIAL_DIFFICULTY, STABILITY_GROWTH_FACTOR
from utils.mastery_algorithm import calculate_next_review_state

# ... (alle Funktionen von get_courses_by_creator bis get_task_details bleiben unverändert) ...

# --- Wissensfestiger (Mastery Learning) Funktionen ---

def get_mastery_tasks_for_course(course_id: str) -> tuple[list | None, str | None]:
    """
    Holt alle Mastery-Aufgaben (is_mastery=True) für einen bestimmten Kurs.
    """
    try:
        # Schritt 1: Hole alle Unit-IDs, die diesem Kurs zugewiesen sind
        units_response = supabase_client.table('course_learning_unit_assignment') \
            .select('unit_id') \
            .eq('course_id', course_id) \
            .execute()
        
        if hasattr(units_response, 'error') and units_response.error:
            return None, f"Fehler beim Abrufen der Kurs-Units: {units_response.error.message}"
        if not hasattr(units_response, 'data') or not units_response.data:
            return [], None
        
        unit_ids = [u['unit_id'] for u in units_response.data]
        
        # Schritt 2: Hole alle Sections dieser Units
        sections_response = supabase_client.table('unit_section') \
            .select('id') \
            .in_('unit_id', unit_ids) \
            .execute()
        
        if hasattr(sections_response, 'error') and sections_response.error:
            return None, f"Fehler beim Abrufen der Sections: {sections_response.error.message}"
        if not hasattr(sections_response, 'data') or not sections_response.data:
            return [], None
        
        section_ids = [s['id'] for s in sections_response.data]
        
        # Schritt 3: Hole alle Mastery-Aufgaben dieser Sections
        tasks_response = supabase_client.table('task') \
            .select('*, unit_section!inner(title, unit_id)') \
            .eq('is_mastery', True) \
            .in_('section_id', section_ids) \
            .execute()
        
        if hasattr(tasks_response, 'error') and tasks_response.error:
            return None, f"Fehler beim Abrufen der Mastery-Aufgaben: {tasks_response.error.message}"
        return tasks_response.data if hasattr(tasks_response, 'data') else [], None
    except Exception as e:
        return None, f"Fehler beim Abrufen der Mastery-Aufgaben: {e}"

def get_next_due_mastery_task(student_id: str, course_id: str) -> tuple[dict | None, str | None]:
    """
    Holt die nächste fällige Wissensfestiger-Aufgabe für einen Schüler in einem Kurs.
    """
    try:
        mastery_tasks, error = get_mastery_tasks_for_course(course_id)
        if error or not mastery_tasks:
            return None, error or "Keine Mastery-Aufgaben in diesem Kurs"

        task_ids = [task['id'] for task in mastery_tasks]
        
        progress_response = supabase_client.table('student_mastery_progress') \
            .select('*') \
            .eq('student_id', student_id) \
            .in_('task_id', task_ids) \
            .execute()

        if hasattr(progress_response, 'error') and progress_response.error:
            return None, f"Fehler beim Abrufen des Lernfortschritts: {progress_response.error.message}"
        
        progress_by_task = {p['task_id']: p for p in progress_response.data} if hasattr(progress_response, 'data') else {}
        
        today = date.today()
        due_tasks = []
        
        for task in mastery_tasks:
            progress = progress_by_task.get(task['id'])
            if not progress:
                due_tasks.append(task)
            else:
                due_date_str = progress.get('next_due_date')
                if due_date_str:
                    try:
                        due_date = datetime.fromisoformat(due_date_str).date()
                        if due_date <= today:
                            task['mastery_progress'] = progress
                            due_tasks.append(task)
                    except (ValueError, TypeError):
                        print(f"Warnung: Ungültiges 'next_due_date' Format für Task {task['id']}: {due_date_str}")
                        due_tasks.append(task)
        
        if not due_tasks:
            return None, "Keine Aufgaben fällig heute. Komm morgen wieder!"
        
        selected_task = random.choice(due_tasks)
        
        if 'mastery_progress' not in selected_task:
            selected_task['mastery_progress'] = progress_by_task.get(selected_task['id'])

        return selected_task, None

    except Exception as e:
        print(f"Exception in get_next_due_mastery_task: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der nächsten Aufgabe: {e}"

def submit_mastery_answer(student_id: str, task_id: str, answer: str) -> tuple[dict | None, str | None]:
    """
    Verarbeitet eine Wissensfestiger-Antwort: KI-Bewertung & Feedback, Speicherung, Fortschritts-Update.
    """
    try:
        task_details, error = get_task_details(task_id)
        if error or not task_details:
            return None, error or f"Aufgabe nicht gefunden: {task_id}"

        submission_history_str = "Dies ist der erste Versuch für diese Aufgabe."
        history, error = get_submission_history(student_id, task_id)
        if error:
            print(f"WARNUNG: Konnte Submission-Historie nicht laden: {error}")
        elif history:
            last_submission = history[-1]
            solution_text = last_submission.get('solution_data', {}).get('text', '(Kein Text)')
            submission_history_str = f"--- LÖSUNG DES LETZTEN VERSUCHS ---\n{solution_text}\n---"

        ai_module = CombinedMasteryFeedbackModule()
        ai_result = ai_module(
            task_details=task_details,
            student_answer=answer,
            submission_history=submission_history_str
        )
        
        q_vec = ai_result.get('q_vec')
        if not q_vec:
            return None, "Fehler bei der KI-Bewertung, kein q_vec erhalten."

        service_client = get_supabase_service_client()
        if not service_client:
            return None, "Service Client nicht verfügbar."

        submission_data = {
            "student_id": student_id,
            "task_id": task_id,
            "solution_data": {"text": answer},
            "ai_criteria_analysis": q_vec,
            "feed_back_text": ai_result.get('feed_back_text'),
            "feed_forward_text": ai_result.get('feed_forward_text'),
            "ai_feedback": f"{ai_result.get('feed_back_text')}\n\n{ai_result.get('feed_forward_text')}",
            "submitted_at": datetime.now(timezone.utc).isoformat()
        }
        
        insert_response = service_client.table('submission').insert(submission_data).execute()
        if hasattr(insert_response, 'error') and insert_response.error:
            print(f"WARNUNG: Konnte Wissensfestiger-Antwort nicht speichern: {insert_response.error}")

        success, error = _update_mastery_progress(student_id, task_id, q_vec, service_client)
        if not success:
            print(f"FEHLER: Konnte Lernfortschritt nicht aktualisieren: {error}")
        
        return ai_result, None

    except Exception as e:
        print(f"Traceback in submit_mastery_answer: {traceback.format_exc()}")
        return None, f"Fehler bei der Verarbeitung der Antwort: {e}"

def _update_mastery_progress(student_id: str, task_id: str, q_vec: dict, service_client) -> tuple[bool, str | None]:
    """
    Interne Funktion zum Aktualisieren des Lernfortschritts.
    """
    if not service_client:
        return False, "Service Client nicht verfügbar."

    try:
        progress_response = service_client.table('student_mastery_progress') \
            .select('*') \
            .eq('student_id', student_id) \
            .eq('task_id', task_id) \
            .maybe_single() \
            .execute()
        
        if hasattr(progress_response, 'error') and progress_response.error:
            return False, f"Fehler beim Abrufen des Fortschritts: {progress_response.error.message}"
        
        current_progress = progress_response.data if hasattr(progress_response, 'data') else None
        
        rating = int(q_vec.get('korrektheit', 0) * 4) + 1
        
        new_state = calculate_next_review_state(
            current_progress=current_progress,
            rating=rating
        )
        
        upsert_data = {
            "student_id": student_id,
            "task_id": task_id,
            "difficulty": new_state['difficulty'],
            "stability": new_state['stability'],
            "state": new_state['state'],
            "last_review_date": new_state['last_review_date'].isoformat(),
            "next_due_date": new_state['next_due_date'].isoformat(),
            "review_history": new_state['review_history']
        }
        
        upsert_response = service_client.table('student_mastery_progress').upsert(upsert_data).execute()
        
        if hasattr(upsert_response, 'error') and upsert_response.error:
            return False, f"Fehler beim Speichern des Fortschritts: {upsert_response.error.message}"
            
        return True, None

    except Exception as e:
        print(f"Exception in _update_mastery_progress: {traceback.format_exc()}")
        return False, f"Fehler bei der Fortschrittsberechnung: {e}"

# ... (Rest der Datei bleibt unverändert) ...
```

---

## Schritt 3: `app/pages/7_Wissensfestiger.py` aktualisieren

Ersetze den Block zur Anzeige des Feedbacks (ca. Zeile 170-175) mit dem neuen Code, der `feed_back_text` und `feed_forward_text` anzeigt.

**Vorher:**
```python
# KI-Feedback
st.markdown("### 💬 Feedback")
# TODO[Phase10][UI]: Ersetze 'reasoning' durch pädagogisches Feedback (KI-Funktion 'generate_pedagogical_feedback' wie bei Nicht-Mastery-Aufgaben)
with st.container(border=True):
    st.markdown(result.get('reasoning', 'Kein Feedback verfügbar.'))
```

**Nachher:**
```python
# KI-Feedback
st.markdown("### 💬 Dein persönliches Feedback")

# Feed-Back
st.markdown("#### 🔍 Wo stehe ich?")
with st.container(border=True):
    st.markdown(result.get('feed_back_text', 'Kein Feed-Back verfügbar.'))

# Feed-Forward
st.markdown("#### 🚀 Wie geht es weiter?")
with st.container(border=True):
    st.markdown(result.get('feed_forward_text', 'Kein Feed-Forward verfügbar.'))
```

---

Nachdem du diese Änderungen vorgenommen hast, wird das Wissensfestiger-Modul das volle pädagogische Feedback nutzen und anzeigen und der Fehler bei der Aufgabenauswahl sollte behoben sein.

```