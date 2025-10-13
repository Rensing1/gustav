# KI-Feedback Optimierungs-Varianten

Dieses Dokument enthält verschiedene Ansätze zur Optimierung der KI-generierten Feedback-Pipeline. Die aktuelle Implementierung analysiert jedes Kriterium einzeln (N LLM-Calls für N Kriterien + 1 für Synthese). Die folgenden Varianten reduzieren die Anzahl der LLM-Calls.

## Variante 1: Batch-Analyse (Alle Kriterien in einem Call)

Diese Variante analysiert alle Kriterien in einem einzigen LLM-Call und behält die strukturierte Ausgabe bei.

### DSPy Signatur

```python
class BatchCriteriaAnalysis(dspy.Signature):
    """
    Analysiert die Schülerlösung im Hinblick auf ALLE angegebenen Kriterien gleichzeitig.
    Gib für jedes Kriterium eine strukturierte Analyse im vorgegebenen Format.
    """
    
    task_description = dspy.InputField(desc="Die von der Lehrkraft gestellte Aufgabe.")
    student_solution = dspy.InputField(desc="Die vom Schüler eingereichte Lösung.")
    solution_hints = dspy.InputField(desc="Die von der Lehrkraft bereitgestellte Musterlösung oder Hinweise.")
    criteria_list = dspy.InputField(desc="JSON-Array mit allen zu prüfenden Kriterien.")
    
    batch_analysis_text = dspy.OutputField(
        desc="""Analysiere JEDES Kriterium einzeln. Für JEDES Kriterium im folgenden Format antworten:

=== KRITERIUM: [Nummer] ===
STATUS: [erfüllt / nicht erfüllt / teilweise erfüllt]
ZITAT: "[Wörtliches Zitat aus der Schülerlösung]"
ANALYSE: [Kurze, objektive Begründung]

Beispiel:
=== KRITERIUM: 1 ===
STATUS: erfüllt
ZITAT: "Die Einleitung führt mit einer rhetorischen Frage ins Thema ein..."
ANALYSE: Das Kriterium "ansprechende Einleitung" ist erfüllt, da eine rhetorische Frage Interesse weckt.

=== KRITERIUM: 2 ===
STATUS: nicht erfüllt
ZITAT: "Am Ende steht nur: Das war's."
ANALYSE: Das Kriterium "ausführliches Fazit" ist nicht erfüllt, da nur ein kurzer Schlusssatz vorhanden ist."""
    )
```

### Implementierung

```python
def process_submission_batch_analysis(
    submission_id: str,
    task_details: Dict,
    submission_data: Dict,
    student_persona: str = "Schüler/in"
) -> Tuple[Optional[Dict], Optional[str]]:
    """Batch-Analyse: Alle Kriterien in einem LLM-Call."""
    
    # Validierung
    if not task_details.get('assessment_criteria'):
        return None, "Keine Bewertungskriterien definiert"
    
    if not submission_data.get('text'):
        return None, "Keine Schülerlösung vorhanden"
    
    # Schritt 1: Batch-Analyse aller Kriterien
    batch_analyzer = dspy.Predict(BatchCriteriaAnalysis)
    
    try:
        import json
        result = batch_analyzer(
            task_description=task_details['instruction'],
            student_solution=submission_data['text'],
            solution_hints=task_details.get('solution_hints', ''),
            criteria_list=json.dumps(task_details['assessment_criteria'], ensure_ascii=False)
        )
        
        # Parse die Batch-Antwort
        final_analysis = {"strengths": [], "weaknesses": []}
        
        if hasattr(result, 'batch_analysis_text'):
            # Parse jeden Kriterien-Block
            blocks = result.batch_analysis_text.split('=== KRITERIUM:')
            
            for i, block in enumerate(blocks[1:]):  # Skip ersten leeren Block
                # Extrahiere Kriterien-Nummer
                lines = block.strip().split('\n')
                if len(lines) < 4:
                    continue
                    
                # Parse Template-Felder aus dem Block
                block_text = '\n'.join(lines)
                analysis_data = parse_template_response(block_text)
                
                # Füge Kriterium hinzu (basierend auf Index)
                if i < len(task_details['assessment_criteria']):
                    analysis_data['criterion'] = task_details['assessment_criteria'][i]
                
                # Sortiere nach Status
                if analysis_data.get('status') == 'erfüllt':
                    final_analysis["strengths"].append(analysis_data)
                else:
                    final_analysis["weaknesses"].append(analysis_data)
        
        # Schritt 2: Pädagogische Synthese (gleich wie vorher)
        feedback_synthesizer = dspy.Predict(GeneratePedagogicalFeedback)
        
        final_feedback = feedback_synthesizer(
            analysis_json=json.dumps(final_analysis, ensure_ascii=False),
            student_persona=student_persona,
            feedback_history=None
        )
        
        if hasattr(final_feedback, 'feed_back_text') and hasattr(final_feedback, 'feed_forward_text'):
            return {
                'feed_back_text': final_feedback.feed_back_text.strip(),
                'feed_forward_text': final_feedback.feed_forward_text.strip(),
                'criteria_analysis': json.dumps(final_analysis, ensure_ascii=False),
                'generated_at': datetime.now().isoformat()
            }, None
            
    except Exception as e:
        return None, f"Fehler bei Batch-Analyse: {str(e)}"
```

## Variante 2: Parallele Analyse mit JSON-Output

Diese Variante gibt direkt ein strukturiertes JSON zurück, ohne Template-Parsing.

### DSPy Signatur

```python
class DirectJSONAnalysis(dspy.Signature):
    """
    Analysiert die Schülerlösung und gibt die Ergebnisse direkt als JSON zurück.
    Dies vermeidet das Template-Parsing und ist robuster.
    """
    
    task_description = dspy.InputField(desc="Die von der Lehrkraft gestellte Aufgabe.")
    student_solution = dspy.InputField(desc="Die vom Schüler eingereichte Lösung.")
    solution_hints = dspy.InputField(desc="Die von der Lehrkraft bereitgestellte Musterlösung oder Hinweise.")
    criteria_list = dspy.InputField(desc="JSON-Array mit allen zu prüfenden Kriterien.")
    
    analysis_json = dspy.OutputField(
        desc="""Gib die Analyse als JSON-Objekt mit folgendem Format zurück:

{
  "strengths": [
    {
      "criterion": "Das erfüllte Kriterium",
      "status": "erfüllt",
      "quote": "Wörtliches Zitat aus der Schülerlösung",
      "analysis": "Kurze Begründung warum erfüllt"
    }
  ],
  "weaknesses": [
    {
      "criterion": "Das nicht erfüllte Kriterium",
      "status": "nicht erfüllt",
      "quote": "Relevantes Zitat oder Hinweis auf Fehlendes",
      "analysis": "Kurze Begründung warum nicht erfüllt"
    }
  ]
}

WICHTIG: Gib NUR das JSON zurück, keine zusätzlichen Erklärungen."""
    )
```

### Implementierung

```python
def process_submission_json_analysis(
    submission_id: str,
    task_details: Dict,
    submission_data: Dict,
    student_persona: str = "Schüler/in"
) -> Tuple[Optional[Dict], Optional[str]]:
    """JSON-Analyse: Direkter JSON-Output ohne Template-Parsing."""
    
    # Validierung
    if not task_details.get('assessment_criteria'):
        return None, "Keine Bewertungskriterien definiert"
    
    if not submission_data.get('text'):
        return None, "Keine Schülerlösung vorhanden"
    
    # Schritt 1: JSON-Analyse
    json_analyzer = dspy.Predict(DirectJSONAnalysis)
    
    try:
        import json
        result = json_analyzer(
            task_description=task_details['instruction'],
            student_solution=submission_data['text'],
            solution_hints=task_details.get('solution_hints', ''),
            criteria_list=json.dumps(task_details['assessment_criteria'], ensure_ascii=False)
        )
        
        # Parse JSON direkt
        if hasattr(result, 'analysis_json'):
            # Versuche JSON zu parsen
            try:
                final_analysis = json.loads(result.analysis_json)
            except json.JSONDecodeError:
                # Fallback: Versuche JSON aus der Antwort zu extrahieren
                import re
                json_match = re.search(r'\{[\s\S]*\}', result.analysis_json)
                if json_match:
                    final_analysis = json.loads(json_match.group(0))
                else:
                    return None, "Konnte JSON nicht aus der Antwort extrahieren"
        else:
            return None, "Keine Analyse erhalten"
        
        # Schritt 2: Pädagogische Synthese (unverändert)
        feedback_synthesizer = dspy.Predict(GeneratePedagogicalFeedback)
        
        final_feedback = feedback_synthesizer(
            analysis_json=json.dumps(final_analysis, ensure_ascii=False),
            student_persona=student_persona,
            feedback_history=None
        )
        
        if hasattr(final_feedback, 'feed_back_text') and hasattr(final_feedback, 'feed_forward_text'):
            return {
                'feed_back_text': final_feedback.feed_back_text.strip(),
                'feed_forward_text': final_feedback.feed_forward_text.strip(),
                'criteria_analysis': json.dumps(final_analysis, ensure_ascii=False),
                'generated_at': datetime.now().isoformat()
            }, None
            
    except Exception as e:
        return None, f"Fehler bei JSON-Analyse: {str(e)}"
```

## Variante 3: Kombinierte Analyse und Synthese (Ein LLM-Call)

Diese Variante kombiniert Analyse und Synthese in einem einzigen LLM-Call für maximale Effizienz.

### DSPy Signatur

```python
class DirectFeedbackGeneration(dspy.Signature):
    """
    Analysiert die Schülerlösung anhand der Kriterien und generiert 
    direkt das pädagogische Feedback in einem Schritt.
    
    Du bist GUSTAV, ein sachlicher und unterstützender Lern-Coach.
    """
    
    task_description = dspy.InputField(desc="Die von der Lehrkraft gestellte Aufgabe.")
    student_solution = dspy.InputField(desc="Die vom Schüler eingereichte Lösung.")
    solution_hints = dspy.InputField(desc="Die von der Lehrkraft bereitgestellte Musterlösung oder Hinweise.")
    criteria_list = dspy.InputField(desc="JSON-Array mit allen zu prüfenden Kriterien.")
    student_persona = dspy.InputField(desc="Beschreibung des Schülers (z.B. '9. Klasse').")
    
    feed_back_text = dspy.OutputField(
        desc="""Der Feedback-Teil, der den Ist-Zustand beschreibt (Wo stehe ich?).
        
        STRUKTUR:
        1. Beginne IMMER mit einer spezifischen, positiven Beobachtung zu einem erfüllten Kriterium
        2. Beschreibe dann klar und wertfrei den wichtigsten Verbesserungspunkt
        3. Beziehe dich auf konkrete Textstellen
        
        REGELN:
        - Bewerte NIE die Person, nur den Text
        - Verwende konkrete Zitate
        - Sei freundlich und ermutigend
        
        BEISPIEL: "Super, ich sehe, dass du eine ansprechende Einleitung mit einer rhetorischen Frage geschrieben hast! Das weckt sofort das Interesse. Mir ist bei der Analyse deines Arguments aufgefallen, dass an der Stelle 'Die Umwelt ist wichtig' noch konkrete Belege fehlen, um es vollständig zu untermauern."""
    )
    
    feed_forward_text = dspy.OutputField(
        desc="""Der Feedback-Teil mit dem nächsten Schritt (Wo geht es als Nächstes hin?).
        
        STRUKTUR:
        1. Formuliere EINEN klaren, umsetzbaren Tipp ODER
        2. Stelle EINE gezielte Frage, die zum Nachdenken anregt
        3. Schließe mit einer Ermutigung
        
        REGELN:
        - Gib NIE die Lösung direkt vor
        - Der Tipp muss sich auf den im feed_back_text genannten Punkt beziehen
        - Sei konkret und handlungsorientiert
        
        BEISPIEL: "Welche Statistiken oder Expertenmeinungen könntest du anführen, um deine Aussage zur Umwelt zu untermauern? Schau mal in deinen Unterlagen nach konkreten Zahlen. Ich bin gespannt auf deine überarbeitete Version!"""
    )
    
    criteria_analysis = dspy.OutputField(
        desc="""Eine kurze JSON-Zusammenfassung der Kriterienanalyse für die Datenbank.
        Format: {"strengths": ["Kriterium 1", "Kriterium 2"], "weaknesses": ["Kriterium 3"]}
        Nur die Kriterienliste, keine Details."""
    )
```

### Implementierung

```python
def process_submission_combined(
    submission_id: str,
    task_details: Dict,
    submission_data: Dict,
    student_persona: str = "Schüler/in"
) -> Tuple[Optional[Dict], Optional[str]]:
    """Kombinierte Analyse und Synthese in einem LLM-Call."""
    
    # Validierung
    if not task_details.get('assessment_criteria'):
        return None, "Keine Bewertungskriterien definiert"
    
    if not submission_data.get('text'):
        return None, "Keine Schülerlösung vorhanden"
    
    # Ein einziger LLM-Call für alles
    combined_generator = dspy.Predict(DirectFeedbackGeneration)
    
    try:
        import json
        from datetime import datetime
        
        result = combined_generator(
            task_description=task_details['instruction'],
            student_solution=submission_data['text'],
            solution_hints=task_details.get('solution_hints', ''),
            criteria_list=json.dumps(task_details['assessment_criteria'], ensure_ascii=False),
            student_persona=student_persona
        )
        
        # Validiere Ergebnis
        if (hasattr(result, 'feed_back_text') and 
            hasattr(result, 'feed_forward_text') and 
            hasattr(result, 'criteria_analysis')):
            
            # Parse criteria_analysis wenn es ein String ist
            criteria_data = result.criteria_analysis
            if isinstance(criteria_data, str):
                try:
                    criteria_data = json.loads(criteria_data)
                except:
                    # Fallback: Erstelle leeres Objekt
                    criteria_data = {"strengths": [], "weaknesses": []}
            
            return {
                'feed_back_text': result.feed_back_text.strip(),
                'feed_forward_text': result.feed_forward_text.strip(),
                'criteria_analysis': json.dumps(criteria_data, ensure_ascii=False),
                'generated_at': datetime.now().isoformat()
            }, None
        else:
            return None, "Unvollständige Ausgabe vom LLM"
            
    except Exception as e:
        return None, f"Fehler bei kombinierter Generierung: {str(e)}"
```

## Variante 4: Optimierte Template-Analyse

Diese Variante behält die atomare Struktur, optimiert aber den Prompt für bessere Compliance.

### DSPy Signatur

```python
class OptimizedBatchAnalysis(dspy.Signature):
    """
    Prüfe ALLE Kriterien und gib ein strukturiertes Ergebnis zurück.
    Sei präzise und objektiv in deiner Analyse.
    """
    
    task_description = dspy.InputField(desc="Die Aufgabenstellung")
    student_solution = dspy.InputField(desc="Die Schülerlösung")
    solution_hints = dspy.InputField(desc="Musterlösung/Hinweise")
    criteria_list = dspy.InputField(desc="Liste der zu prüfenden Kriterien")
    
    analysis_output = dspy.OutputField(
        desc="""Analysiere jedes Kriterium. Nutze dieses Format:

[KRITERIUM 1: <Name des Kriteriums>]
Status: erfüllt
Beleg: "Zitat aus der Schülerlösung"
Grund: Kurze Begründung

[KRITERIUM 2: <Name des Kriteriums>]
Status: nicht erfüllt
Beleg: "Zitat oder Hinweis auf Fehlendes"
Grund: Kurze Begründung

Verwende NUR diese Status-Werte: erfüllt, nicht erfüllt, teilweise erfüllt"""
    )
```

### Implementierung mit besserem Parsing

```python
def parse_optimized_template(response: str, criteria_list: List[str]) -> Dict:
    """Optimiertes Parsing für das vereinfachte Template-Format."""
    
    final_analysis = {"strengths": [], "weaknesses": []}
    
    # Split by criterion blocks
    blocks = re.split(r'\[KRITERIUM \d+:', response)
    
    for block in blocks[1:]:  # Skip first empty
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
            
        # Extract criterion name from first line
        criterion_match = re.match(r'([^\]]+)\]', lines[0])
        if not criterion_match:
            continue
        criterion = criterion_match.group(1).strip()
        
        # Initialize result
        result = {
            'criterion': criterion,
            'status': None,
            'quote': None,
            'analysis': None
        }
        
        # Parse fields
        for line in lines[1:]:
            if line.startswith('Status:'):
                result['status'] = line.replace('Status:', '').strip().lower()
            elif line.startswith('Beleg:'):
                result['quote'] = line.replace('Beleg:', '').strip().strip('"')
            elif line.startswith('Grund:'):
                result['analysis'] = line.replace('Grund:', '').strip()
        
        # Categorize
        if result['status'] == 'erfüllt':
            final_analysis["strengths"].append(result)
        else:
            final_analysis["weaknesses"].append(result)
    
    return final_analysis

def process_submission_optimized(
    submission_id: str,
    task_details: Dict,
    submission_data: Dict,
    student_persona: str = "Schüler/in"
) -> Tuple[Optional[Dict], Optional[str]]:
    """Optimierte Template-Analyse mit besserem Parsing."""
    
    # Validierung
    if not task_details.get('assessment_criteria'):
        return None, "Keine Bewertungskriterien definiert"
    
    if not submission_data.get('text'):
        return None, "Keine Schülerlösung vorhanden"
    
    # Schritt 1: Optimierte Batch-Analyse
    analyzer = dspy.Predict(OptimizedBatchAnalysis)
    
    try:
        import json
        from datetime import datetime
        
        # Erstelle nummerierte Kriterienliste für besseres Parsing
        criteria_text = "\n".join([
            f"{i+1}. {criterion}" 
            for i, criterion in enumerate(task_details['assessment_criteria'])
        ])
        
        result = analyzer(
            task_description=task_details['instruction'],
            student_solution=submission_data['text'],
            solution_hints=task_details.get('solution_hints', ''),
            criteria_list=criteria_text
        )
        
        # Parse mit optimiertem Parser
        if hasattr(result, 'analysis_output'):
            final_analysis = parse_optimized_template(
                result.analysis_output,
                task_details['assessment_criteria']
            )
        else:
            return None, "Keine Analyse erhalten"
        
        # Schritt 2: Pädagogische Synthese (unverändert)
        feedback_synthesizer = dspy.Predict(GeneratePedagogicalFeedback)
        
        final_feedback = feedback_synthesizer(
            analysis_json=json.dumps(final_analysis, ensure_ascii=False),
            student_persona=student_persona,
            feedback_history=None
        )
        
        if hasattr(final_feedback, 'feed_back_text') and hasattr(final_feedback, 'feed_forward_text'):
            return {
                'feed_back_text': final_feedback.feed_back_text.strip(),
                'feed_forward_text': final_feedback.feed_forward_text.strip(),
                'criteria_analysis': json.dumps(final_analysis, ensure_ascii=False),
                'generated_at': datetime.now().isoformat()
            }, None
            
    except Exception as e:
        return None, f"Fehler bei optimierter Analyse: {str(e)}"
```

## Vergleich der Varianten

| Variante | LLM-Calls | Vorteile | Nachteile |
|----------|-----------|----------|-----------|
| **Aktuell** | N+1 (N Kriterien + 1 Synthese) | Fokussierte Analyse pro Kriterium | Viele API-Calls, langsam |
| **Variante 1** | 2 (Batch + Synthese) | Strukturierte Ausgabe, moderate Reduktion | Template-Parsing nötig |
| **Variante 2** | 2 (JSON + Synthese) | Robustes JSON-Format | JSON-Parsing Fehleranfälligkeit |
| **Variante 3** | 1 (Alles kombiniert) | Maximale Effizienz | Weniger Transparenz, schwieriger zu debuggen |
| **Variante 4** | 2 (Optimiert + Synthese) | Bessere Template-Compliance | Noch immer 2 Calls |

## Testbeispiel

Hier ein Beispiel zum Testen der verschiedenen Varianten:

### Aufgabe
```python
task_details = {
    'instruction': "Schreibe einen Kommentar zum Thema 'Sollten Handys in der Schule erlaubt sein?'",
    'assessment_criteria': [
        "Klare Positionierung (Pro oder Contra)",
        "Mindestens drei überzeugende Argumente",
        "Berücksichtigung der Gegenseite",
        "Strukturierter Aufbau (Einleitung, Hauptteil, Schluss)",
        "Verwendung von Beispielen"
    ],
    'solution_hints': "Ein guter Kommentar nimmt klar Stellung, begründet diese mit mehreren Argumenten und geht auch auf Gegenargumente ein."
}
```

### Schülerlösung
```python
submission_data = {
    'text': """Handys in der Schule - ja oder nein?

Ich finde, dass Handys in der Schule erlaubt sein sollten. 

Erstens können wir mit Handys schnell Informationen für den Unterricht recherchieren. Wenn wir zum Beispiel ein Wort nicht kennen, können wir es nachschlagen.

Zweitens sind Handys wichtig für die Sicherheit. Wenn etwas passiert, können wir unsere Eltern anrufen.

Drittens können wir mit Apps besser lernen. Es gibt viele gute Lern-Apps für Mathe und Sprachen.

Natürlich sagen manche, dass Handys ablenken. Das stimmt schon, aber man könnte Regeln machen, wann man sie benutzen darf.

Also sollten Handys erlaubt sein, aber mit klaren Regeln."""
}
```

## Integration in die App

Um eine Variante zu testen, ersetze in `app/ai/processor.py` die Funktion `process_submission_with_atomic_analysis` mit einer der obigen Implementierungen. 

Beispiel für Variante 3 (kombiniert):

```python
# In app/ai/processor.py
from .signatures import DirectFeedbackGeneration  # Neue Signatur importieren

# Ersetze die bestehende Funktion
process_submission_with_atomic_analysis = process_submission_combined
```

## Empfehlung

Für maximale Effizienz empfehle ich **Variante 3** (Kombinierte Analyse und Synthese), da sie:
- Nur 1 LLM-Call benötigt
- Direkt pädagogisches Feedback generiert
- Die Kriterien implizit in der Feedbackgenerierung berücksichtigt

Falls mehr Transparenz gewünscht ist, wäre **Variante 2** (JSON-Output) eine gute Alternative mit 2 Calls und strukturierter Zwischenausgabe.
