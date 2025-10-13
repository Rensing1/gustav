# app/ai/signatures.py
import dspy

class GenerateFocusedFeedback(dspy.Signature):
    """
    Du bist ein hilfreicher und pädagogisch versierter Feedback-Assistent.
    Generiere spezifisches, konstruktives und lernförderliches Feedback für die Schülerlösung.
    Berücksichtige dabei die Aufgabenstellung und insbesondere den vom Lehrer angegebenen Feedback-Fokus.
    """
    # --- INPUT Felder ---
    task_instruction = dspy.InputField(desc="Die ursprüngliche Anweisung der Aufgabe.")
    student_solution = dspy.InputField(desc="Die vom Schüler eingereichte Textlösung.")
    feedback_focus = dspy.InputField(
        desc="Vom Lehrer definierte Aspekte oder Kriterien, die im Feedback besonders berücksichtigt werden sollen.",
        optional=True
    )

    # --- OUTPUT Feld ---
    feedback_text = dspy.OutputField(
        desc="Formuliere das Feedback. Gehe konkret auf die Lösung und den Feedback-Fokus ein. Nenne Stärken und Verbesserungsvorschläge. Sei freundlich und ermutigend. Antworte NUR mit dem reinen Feedback-Text, ohne zusätzliche Einleitung oder Verabschiedung."
    )

class AnalyseSingleCriterion(dspy.Signature):
    """Analysiert die Schülerlösung im Hinblick auf EIN spezifisches Kriterium."""
    
    task_description = dspy.InputField(desc="Die von der Lehrkraft gestellte Aufgabe.")
    student_solution = dspy.InputField(desc="Die vom Schüler eingereichte Lösung.")
    solution_hints = dspy.InputField(desc="Die von der Lehrkraft bereitgestellte Musterlösung oder Hinweise zur sachlichen Korrektheit.")
    criterion_to_check = dspy.InputField(desc="Das eine Kriterium, das jetzt geprüft werden soll.")
    
    single_analysis_text = dspy.OutputField(
        desc="""Strukturierte Antwort im folgenden Format (GENAU SO, mit Großbuchstaben für die Labels):
STATUS: [Wähle EINES: erfüllt / nicht erfüllt / teilweise erfüllt]
ZITAT: "[Kopiere ein wörtliches Zitat aus der Schülerlösung]"
ANALYSE: [Schreibe eine kurze, objektive Begründung]"""
    )

class GeneratePedagogicalFeedback(dspy.Signature):
    """Formuliert auf Basis einer Analyse ein pädagogisch wertvolles Feedback."""
    
    # Flexibler Input - kann JSON oder strukturierter Text sein
    analysis_input = dspy.InputField(
        desc="""Die Analyse der Schülerlösung. 
        Kann entweder ein JSON-Objekt oder eine strukturierte Textanalyse sein.
        Bei Text: Achte auf Status-Angaben (erfüllt/nicht erfüllt) für jedes Kriterium."""
    )
    student_solution = dspy.InputField(
        desc="Die Original-Schülerlösung, auf die sich das Feedback bezieht"
    )
    feedback_history = dspy.InputField(
        desc="Der Verlauf der bisherigen Feedback-Runden für diese Aufgabe.",
        optional=True
    )
    
    # Pädagogische Regeln als Teil der Signatur-Beschreibung
    feed_back_text = dspy.OutputField(
        desc="""Formuliere den Feed-Back Teil (Wo stehe ich?).
        
        WICHTIGE REGELN:
        - Beginne IMMER mit einer spezifischen positiven Beobachtung
        - Nenne dann den wichtigsten Verbesserungspunkt
        - Beziehe dich auf konkrete Stellen aus der Schülerlösung
        - Bewerte NIE die Person, nur den Text
        - Sei freundlich und ermutigend"""
    )
    
    feed_forward_text = dspy.OutputField(
        desc="""Formuliere den Feed-Forward Teil (Wo geht es hin?).
        
        WICHTIGE REGELN:
        - Gib EINEN konkreten, umsetzbaren Tipp ODER
        - Stelle EINE Frage, die zum Nachdenken anregt
        - Schließe mit einer Ermutigung
        - Gib NIE die Lösung direkt vor"""
    )


class MasteryAssessment(dspy.Signature):
    """
    Bewerte die Schülerantwort präzise auf einer Skala von 1-5 basierend auf
    inhaltlicher Korrektheit, Vollständigkeit und Verständnistiefe.
    
    Bewertungsskala:
    5 = Vollständig korrekt und klar formuliert; zeigt tiefes Verständnis
    4 = Überwiegend korrekt mit kleinen Ungenauigkeiten oder Lücken  
    3 = Grundlegendes Verständnis vorhanden, aber wichtige Aspekte fehlen
    2 = Ansatzweise richtig, aber größere Fehler oder Verständnislücken
    1 = Größtenteils falsch oder zeigt kein Verständnis des Konzepts
    
    Sei streng aber fair. Ein Score von 5 sollte nur für wirklich exzellente Antworten vergeben werden.
    """
    
    task_instruction = dspy.InputField(desc="Die Aufgabenstellung, die der Schüler bearbeiten soll.")
    assessment_criteria = dspy.InputField(desc="Bewertungskriterien als JSON-Array mit den wichtigsten zu prüfenden Punkten.")
    solution_hints = dspy.InputField(desc="Optionale Lösungshinweise oder Musterlösung zur Orientierung.", optional=True)
    student_answer = dspy.InputField(desc="Die Antwort des Schülers, die bewertet werden soll.")
    
    score = dspy.OutputField(desc="Numerische Bewertung: Gib GENAU EINE Zahl von 1 bis 5 zurück. Nur die Zahl, nichts anderes.")
    reasoning = dspy.OutputField(desc="Kurze Begründung der Bewertung in 2-3 Sätzen. Erkläre, was gut war und was gefehlt hat.")


class AnalyzeSubmission(dspy.Signature):
    """Analysiert die Schülerlösung anhand aller vorgegebenen Kriterien."""
    
    task_description = dspy.InputField(desc="Die Aufgabenstellung")
    student_solution = dspy.InputField(desc="Die Schülerlösung")
    solution_hints = dspy.InputField(desc="Lösungshinweise/Musterlösung")
    criteria_list = dspy.InputField(desc="Liste der zu prüfenden Kriterien")
    
    analysis_text = dspy.OutputField(
        desc="""Analysiere JEDES Kriterium systematisch. Nutze für jedes Kriterium dieses Format:

**Kriterium: [Name des Kriteriums]**
Status: [erfüllt/nicht erfüllt/teilweise erfüllt]
Beleg: "[Relevantes Zitat aus der Schülerlösung]"
Analyse: [Objektive Begründung der Bewertung]

Gehe alle Kriterien der Reihe nach durch. Sei präzise und objektiv."""
    )

class ExtractTextFromImage(dspy.Signature):
    """
    Du bist ein Transkriptionsassistent für deutsche Texte.
    Extrahiere den handschriftlichen Text aus dem bereitgestellten Bild präzise und vollständig.
    
    Regeln:
    - Schreibe nur den Text, der wirklich im Bild steht
    - Behalte deutsche Umlaute (ä, ö, ü, ß)
    - Markiere unleserliche Stellen mit [UNLESERLICH]
    - Keine Erklärungen oder Kommentare
    - Nur der reine transkribierte Text
    """
    
    image = dspy.InputField(desc="Bild mit handschriftlichem Text", format=dspy.Image)
    extracted_text = dspy.OutputField(desc="Der exakt transkribierte Text aus dem Bild")