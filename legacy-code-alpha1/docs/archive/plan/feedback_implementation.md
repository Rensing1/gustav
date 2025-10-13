# Implementierungskonzept: GUSTAVs KI-gestütztes Feedback-System

## Stand: 2025-08-01

## Aktueller Implementierungsstatus

### ✅ Erfolgreich implementiert:

1. **Zweistufige "Atomare Analyse"-Pipeline**
   - Atomare Analyse pro Kriterium funktioniert (`processor.py`)
   - Pädagogische Synthese generiert Feed-Back und Feed-Forward getrennt
   - Robustes Template-basiertes Parsing statt JSON

2. **DSPy Signaturen**
   - `AnalyseSingleCriterion`: Analysiert ein Kriterium mit Template-Output
   - `GeneratePedagogicalFeedback`: Erzeugt strukturiertes pädagogisches Feedback

3. **Datenbankstruktur**
   - Migration 20250801123332 erfolgreich durchgeführt
   - `feedback_focus` aufgeteilt in `assessment_criteria` (JSONB Array) und `solution_hints` (TEXT)
   - Neue Spalten `feed_back_text` und `feed_forward_text` in submission Tabelle

4. **Service-Integration**
   - `service.py` nutzt die neue atomare Pipeline
   - Fehlerbehandlung und Logging implementiert
   - Abwärtskompatibilität durch kombiniertes Feedback gewährleistet

5. **UI-Integration** ✅
   - Teacher-UI: Eingabe von bis zu 5 Bewertungskriterien als separate Felder (`detail_editor.py`)
   - Teacher-UI: Eingabefeld für Lösungshinweise implementiert
   - Student-UI: Getrennte Anzeige von Feed-Back ("Wo du stehst") und Feed-Forward ("Dein nächster Schritt")
   - Live-Unterricht View: Vorschau und Bearbeitung des strukturierten Feedbacks
   - Fallback für altes Feedback-Format gewährleistet

### 🚧 TODO / Nächste Schritte:

1. **Prompt-Optimierung**
   - Few-Shot-Beispiele für bessere Feedback-Qualität
   - Persona-Anpassung (Klassenstufe aus Profil)
   - Feedback-Historie für Mehrfachabgaben implementieren

2. **Performance**
   - Parallelisierung der atomaren Analysen
   - Caching für identische Kriterien
   - Progress-Anzeige während Analyse

3. **Erweiterte Features**
   - Mehrfachabgaben mit Feedback-Historie
   - Gewichtung von Bewertungskriterien
   - Spezifische Prompts für unterschiedliche Aufgabentypen

## 1. Zielsetzung und Leitprinzipien

Dieses Dokument beschreibt die technische und konzeptionelle Architektur für die KI-gestützte Feedback-Engine der Lernplattform. Das Ziel ist die Entwicklung eines robusten, skalierbaren und pädagogisch wertvollen Systems, das in der Lage ist, Schülern formatives Feedback zu geben.

Die Implementierung folgt zwei zentralen Leitprinzipien:

1.  **Pädagogische Fundierung:** Das generierte Feedback muss den in `feedback_science.md` dargelegten wissenschaftlichen Kriterien genügen. Im Fokus stehen aufgabenbezogenes Feed-Back und Feed-Forward in einer unterstützenden, nicht-wertenden Tonalität.
2.  **Technische Robustheit:** Die Architektur muss den Einschränkungen eines lokal betriebenen 8b-Sprachmodells Rechnung tragen. Im Mittelpunkt stehen Zuverlässigkeit, Steuerbarkeit und Effizienz, umgesetzt mit dem DSPy-Framework.

Es ist zu beachten, dass der Schüler seine Aufgaben gegebenfalls mehrfach abgeben kann. Der Lehrer bestimmt dies bei der Erstellung von Aufgaben (Standard: max. 1 Abgabe).

## 2. Architektur: Die zweistufige "Atomare Analyse"-Pipeline

Um die Komplexität für das 8b-Modell zu reduzieren und die Zuverlässigkeit zu maximieren, wird eine zweistufige Pipeline implementiert. Anstatt eines einzigen, komplexen LLM-Aufrufs, der alles auf einmal erledigen soll, zerlegen wir den Prozess in logische, voneinander getrennte Schritte.

### 2.1. Grundprinzip

Die Kernidee ist, die **objektive Analyse** der Schülerlösung von der **pädagogischen Formulierung** des Feedbacks zu trennen. Wir vermeiden das fehleranfällige Generieren eines einzigen, großen JSON-Objekts, indem wir die Analyse in atomare Einheiten zerlegen.

### 2.2. Schritt 1: Der "Analytiker" (Atomare Analyse pro Kriterium)

In diesem Schritt wird die Schülerlösung nicht als Ganzes, sondern Kriterium für Kriterium analysiert. Dies geschieht in einer Schleife in der Anwendungslogik. Für jedes vom Lehrer definierte Bewertungskriterium wird ein fokussierter LLM-Aufruf gestartet.

*   **Aufgabe:** Bewerte die Schülerlösung im Hinblick auf *ein einziges, spezifisches Kriterium*.
*   **Kontext:** Erhält die Aufgabenstellung, die Schülerlösung, die Lösungshinweise und das eine zu prüfende Kriterium.
*   **Output:** Ein sehr kleines, einfach strukturiertes JSON-Objekt, das nur die Analyse für dieses eine Kriterium enthält.

### 2.3. Schritt 2: Der "Pädagoge" (Synthese des Feedbacks)

Nachdem die Analyse-Schleife durchgelaufen ist, werden die einzelnen Analyse-JSONs zu einem Gesamt-Analyseobjekt zusammengefügt. Dieses strukturierte Objekt wird dann an den zweiten, pädagogischen Schritt übergeben.

*   **Aufgabe:** Formuliere aus der vollständigen, strukturierten Analyse ein kohärentes, pädagogisch wertvolles Feedback.
*   **Kontext:** Erhält das Gesamt-Analyseobjekt und die optionale Feedback-Historie.
*   **Output:** Zwei separate, aber zusammenhängende Textteile: ein **Feed-Back** und ein **Feed-Forward**.

### 2.4. Visuelles Flussdiagramm

```
[START]
   |
   V
[Inputs: Aufgabe, Lösung, Kriterien (Liste), Lösungshinweise, Historie]
   |
   V
/-------------------------------------\
|  Analyse-Schleife (Schritt 1)       |
|                                     |
|  FOR each `kriterium` in `Kriterien`: |
|     |                               |
|     V                               |
|  [LLM-Aufruf: AnalyseSingleCriterion]----> Input: (Aufgabe, Lösung, kriterium, Lösungshinweise)
|     |                               |
|     V                               |
|  [Output: Kleines Analyse-JSON]     |
|     |                               |
|  <--- Sammle JSONs in `final_analysis` |
|                                     |
\-------------------------------------/
   |
   V
[Input für Schritt 2: `final_analysis`, `Historie`]
   |
   V
[LLM-Aufruf: GeneratePedagogicalFeedback]
   |
   V
[Output: `feed_back_text`, `feed_forward_text`]
   |
   V
[ENDE]
```

## 3. Detail-Spezifikation der DSPy-Komponenten

Die Architektur wird durch zwei klar definierte DSPy-Signaturen umgesetzt.

### 3.1. Signatur für Schritt 1: `AnalyseSingleCriterion`

Diese Signatur ist das Arbeitspferd der Analyse-Schleife. Sie ist bewusst schlank und fokussiert gehalten.

```python
import dspy

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
```

**Begründung:**
*   `solution_hints` wird hier benötigt, damit die sachliche Korrektheit direkt bei der Analyse geprüft werden kann.
*   **Update 2025-08-01**: Da viele LLMs (insbesondere gemma3:12b) Schwierigkeiten mit der Generierung von validem JSON haben, wurde auf ein strukturiertes Text-Template umgestellt. Dies erhöht die Robustheit erheblich.

### 3.2. Signatur für Schritt 2: `GeneratePedagogicalFeedback`

Diese Signatur ist für die Kommunikation mit dem Schüler zuständig. Ihre wichtigste Eigenschaft ist die Aufteilung des Outputs in zwei separate Felder, um die pädagogische Struktur zu garantieren.

```python
class GeneratePedagogicalFeedback(dspy.Signature):
    """Formuliert auf Basis einer strukturierten Analyse ein pädagogisch wertvolles Feedback."""

    analysis_json = dspy.InputField(desc="Das zusammengefasste JSON-Objekt mit der Analyse aller Kriterien.")
    student_persona = dspy.InputField(desc="Informationen zum Schüler, z.B. '8. Klasse', um den Ton anzupassen.")
    feedback_history = dspy.InputField(
        desc="Der Verlauf der bisherigen Feedback-Runden für diese Aufgabe.",
        required=False
    )

    feed_back_text = dspy.OutputField(desc="Der Teil des Feedbacks, der den Ist-Zustand beschreibt (Wo stehe ich?), beginnend mit einem positiven Einstieg.")
    feed_forward_text = dspy.OutputField(desc="Der Teil des Feedbacks, der einen konkreten, umsetzbaren nächsten Schritt vorschlägt (Wo geht es als Nächstes hin?).")
```

**Begründung:**
*   Die Trennung in `feed_back_text` und `feed_forward_text` ist eine entscheidende Maßnahme zur Qualitätssicherung. Sie **zwingt** das LLM, beide für effektives Feedback notwendigen Komponenten zu generieren.
*   Diese Struktur ermöglicht es dem Frontend, die beiden Teile des Feedbacks unterschiedlich darzustellen (z.B. den Feed-Forward als hervorgehobene "Nächster Schritt"-Box), was die Verständlichkeit und Handlungsorientierung für den Schüler erhöht.

## 4. Der Orchestrierungs-Prozess (Anwendungslogik)

Der folgende Pseudo-Code skizziert, wie die DSPy-Module in der Anwendungslogik gesteuert werden.

```python
# 4.1. Vorbereitung
# Inputs aus dem System laden: task, solution, teacher_criteria (Liste), hints, history
atomic_analyzer = dspy.Predict(AnalyseSingleCriterion)
feedback_synthesizer = dspy.Predict(GeneratePedagogicalFeedback)
final_analysis_obj = {"strengths": [], "weaknesses": []}

# 4.2. Die Analyse-Schleife
for criterion in teacher_criteria:
    try:
        # Führe für jedes Kriterium einen fokussierten LLM-Aufruf durch
        result = atomic_analyzer(
            task_description=task,
            student_solution=solution,
            solution_hints=hints,
            criterion_to_check=criterion
        )
        # Parse die strukturierte Text-Antwort
        analysis_data = parse_template_response(result.single_analysis_text)
        analysis_data['criterion'] = criterion # Füge das Kriterium für den Kontext hinzu

        # Sortiere das Ergebnis in die finale Struktur ein
        if analysis_data['status'] == 'erfüllt':
            final_analysis_obj["strengths"].append(analysis_data)
        else:
            final_analysis_obj["weaknesses"].append(analysis_data)
            
    except Exception as e:
        # Robuste Fehlerbehandlung für den Fall, dass ein einzelner Aufruf fehlschlägt
        print(f"Fehler bei der Analyse des Kriteriums '{criterion}': {e}")

# 4.3. Die Synthese
# Stelle sicher, dass das analysis_json nicht leer ist
if final_analysis_obj["strengths"] or final_analysis_obj["weaknesses"]:
    final_feedback = feedback_synthesizer(
        analysis_json=json.dumps(final_analysis_obj),
        student_persona="Schüler/in der 9. Klasse",
        feedback_history=history
    )
    # Gib die beiden separaten Textteile an das Frontend weiter
    # z.B. display_feedback(final_feedback.feed_back_text, final_feedback.feed_forward_text)
else:
    # Fallback, falls die gesamte Analyse fehlschlägt
    print("Es konnte leider kein automatisches Feedback generiert werden.")
```

## 5. Begründung zentraler Entscheidungen und Alternativen

| Thema | Unsere Entscheidung & Begründung | Betrachtete Alternativen & Warum verworfen |
| :--- | :--- | :--- |
| **Struktur der Analyse** | **Atomare Analyse-Schleife:** Jeder LLM-Aufruf im ersten Schritt erzeugt nur ein winziges, flaches JSON pro Kriterium. **Begründung:** Maximale Zuverlässigkeit und drastisch reduzierte Fehleranfälligkeit bei der JSON-Generierung durch ein kleines 8b-Modell. | **Ein großer JSON-Blob:** Ein einziger LLM-Aufruf generiert ein komplexes, verschachteltes JSON. **Verworfen weil:** Zu fehleranfällig für ein 8b-Modell. Ein Syntaxfehler macht das gesamte Ergebnis unbrauchbar. |
| **Struktur des Feedbacks** | **Separate Felder für Feed-Back & Feed-Forward:** Der "Pädagoge" generiert zwei getrennte Text-Outputs. **Begründung:** Garantiert die Vollständigkeit des Feedbacks und ermöglicht eine flexiblere, klarere Darstellung im Frontend. | **Ein einzelner Textblock:** Das LLM formuliert einen einzigen, kohärenten Text. **Verworfen weil:** Geringere Zuverlässigkeit (Gefahr, dass der Feed-Forward vergessen wird) und starre Darstellungsmöglichkeiten in der UI. |
| **Kontext-Bereitstellung (Lehrer-UI)** | **Strukturierte Eingabefelder:** Die UI bietet separate Felder für "Bewertungskriterien" und "Lösungshinweise". **Begründung:** Erzwingt klare, strukturierte Eingaben, was zu einem sauberen, "rauschfreien" Prompt für die KI führt – überlebenswichtig für ein kleines Modell. | **Eine einzige "Magic Textbox":** Ein großes Textfeld für alle Anweisungen. **Verworfen weil:** Führt zu unstrukturierten, mehrdeutigen Prompts, die die Leistung und Zuverlässigkeit der KI stark beeinträchtigen. |
| **Umgang mit Aufgabentypen** | **Universeller, datengesteuerter Ansatz:** Eine einzige, agnostische Pipeline, deren Verhalten durch die vom Lehrer gelieferten `evaluation_criteria` gesteuert wird. **Begründung:** Extrem wartungs- und skalierbar. | **Spezialisierte Prompts/Signaturen:** Für jeden Aufgabentyp eine eigene Signatur. **Verworfen weil:** Hoher Entwicklungs- und Wartungsaufwand. |
| **Dialogfähigkeit (Historie)** | **Historie als Input für den "Pädagogen" (Schritt 2):** Die Historie wird nur zur Formulierung des Feedbacks genutzt, nicht zur Analyse. **Begründung:** Gewährleistet eine objektive Analyse der *aktuellen* Lösung in Schritt 1. | **Historie als Input für den "Analytiker" (Schritt 1):** Die KI analysiert die neue Lösung im Licht der alten. **Verworfen weil:** Gefahr der "Voreingenommenheit" bei der Analyse. |

## 6. Prompt-Design: Die Einbettung der Pädagogik

Die Einhaltung der pädagogischen Kriterien wird durch ein striktes Regelwerk im Prompt des "Pädagogen" (`GeneratePedagogicalFeedback`) sichergestellt.

**Auszug aus dem Kern-Prompt für `GeneratePedagogicalFeedback`:**

```
Du bist GUSTAV, ein sachlicher und unterstützender Lern-Coach.

### Absolute Regeln:
1.  **Spezifität:** Beziehe dich IMMER auf konkrete Zitate aus der Analyse.
2.  **Keine Personenbewertung:** Bewerte NIEMALS die Person. Beziehe dich IMMER auf den Text.
3.  **Keine Prozessbewertung:** Kommentiere NIEMALS den Lernprozess.
4.  **Keine Lösungen:** Gib NIEMALS die Lösung direkt vor.

### Deine Aufgabe:
Basierend auf der folgenden Analyse, fülle die beiden Felder `feed_back_text` und `feed_forward_text` aus. Wenn eine `feedback_history` vorhanden ist, erkenne Fortschritte an.

### Analyse:
{{analysis_json}}
{{feedback_history}}

---
### FELD 1: `feed_back_text`
Beginne IMMER mit einer spezifischen, positiven Beobachtung. Beschreibe dann klar und wertfrei den wichtigsten Verbesserungspunkt.
Beispiel: "Super, ich sehe, du hast den Hinweis zur Einleitung umgesetzt! Sie ist jetzt viel prägnanter. Mir ist bei der Analyse deines Arguments aufgefallen, dass an der Stelle '...' noch ein Beleg fehlt, um es vollständig zu untermauern."

### FELD 2: `feed_forward_text`
Formuliere EINEN klaren, umsetzbaren Tipp oder stelle EINE gezielte Frage, die dem Schüler hilft, genau den im `feed_back_text` genannten Punkt zu verbessern. Schließe mit einer Ermutigung.
Beispiel: "Welche Textstelle könntest du zitieren, um deine Behauptung zu untermauern? Ich bin gespannt auf deine nächste Version!"
```

## 7. Performance-Betrachtung und Optimierungspotenziale

Die gewählte "Atomare Analyse"-Architektur priorisiert Zuverlässigkeit und Robustheit über rohe Geschwindigkeit. Statt eines großen LLM-Aufrufs werden N+1 kleinere Aufrufe getätigt (N = Anzahl der Kriterien). Dies führt zu einem erhöhten Rechenaufwand, da der Kontext (Schülerlösung, Aufgabenstellung) mehrfach verarbeitet wird.

**Abwägung:** Dieser höhere Aufwand ist ein bewusster Kompromiss. Ein System, das zuverlässig in 99% der Fälle ein Ergebnis liefert, ist für den Bildungskontext wertvoller als ein schnelleres System, das aufgrund von Syntaxfehlern häufiger versagt.

**Maßnahmen zur Performance-Optimierung (Spätere Umsetzung):**

Die folgenden Maßnahmen können in späteren Entwicklungsphasen implementiert werden, um die Latenz zu reduzieren, ohne die Robustheit zu opfern:

*   **Asynchrone/Parallele Ausführung:** Die N Analyse-Aufrufe in der Schleife sind voneinander unabhängig. Sie können parallelisiert werden, sodass die Gesamtlatenz der Analysephase sich an der des langsamsten Einzelaufrufs orientiert, nicht an der Summe aller Aufrufe. Dies ist die wichtigste Optimierungsmaßnahme.
*   **Intelligentes UI/UX-Design:** Während die Analyse läuft, kann dem Nutzer der Fortschritt angezeigt werden ("Analysiere Kriterium 2 von 5..."). Dies verbessert die wahrgenommene Geschwindigkeit und macht das Warten transparenter.
*   **Caching:** Ergebnisse von `AnalyseSingleCriterion` für eine identische Kombination aus Schülerlösung und Kriterium können zwischengespeichert werden, um wiederholte Berechnungen zu vermeiden.

## 8. Fazit

Dieses Implementierungskonzept skizziert eine robuste und pädagogisch fundierte Architektur. Durch die **atomare Analyse** wird das Problem der Zuverlässigkeit kleiner LLMs adressiert. Durch die **Trennung von Feed-Back und Feed-Forward in separate Outputs** und ein **regelbasiertes Prompt-Design** wird sichergestellt, dass das generierte Feedback den wissenschaftlichen Kriterien entspricht und im Frontend optimal dargestellt werden kann. Die nächsten Schritte umfassen die konkrete Implementierung der DSPy-Module und den Aufbau eines "Gold-Standard"-Datensatzes, um das System kontinuierlich zu optimieren.

## 9. Template-basiertes Parsing (Update 2025-08-01)

### 9.1. Problemstellung

In der Praxis zeigte sich, dass viele lokale LLMs (insbesondere gemma3:12b) erhebliche Schwierigkeiten haben, konsistent valides JSON zu generieren. Dies führte dazu, dass die atomare Analyse regelmäßig fehlschlug, obwohl das LLM die Aufgabe inhaltlich verstanden hatte.

### 9.2. Lösung: Strukturierte Text-Templates

Anstatt JSON zu verlangen, nutzen wir nun ein einfaches, für Menschen und Maschinen lesbares Template-Format:

```
STATUS: erfüllt
ZITAT: "Die deutsche Verfassung (Grundgesetz) hat ein besonderes Gesetz, das sogenannte §21."
ANALYSE: Der Schüler nennt korrekt den relevanten Paragraphen des Grundgesetzes.
```

### 9.3. Template-Parser

Der Parser verwendet robuste Regex-Patterns, um die drei Felder zu extrahieren:
- **STATUS**: Sucht nach dem Label und einem der drei erlaubten Werte
- **ZITAT**: Extrahiert Text zwischen Anführungszeichen (mit Fallbacks)
- **ANALYSE**: Nimmt allen Text nach dem Label bis zum Ende oder nächsten Label

### 9.4. Vorteile

1. **Robustheit**: Funktioniert zuverlässig mit allen LLMs
2. **Transparenz**: Einfach zu debuggen und zu verstehen
3. **Flexibilität**: Teilweise Ergebnisse sind möglich (z.B. nur Status)
4. **Wartbarkeit**: Parser kann leicht angepasst werden

### 9.5. Zukünftige Erweiterung: DSPy TypedPredictor

Als zukünftige Alternative könnte DSPy's TypedPredictor mit Pydantic-Modellen evaluiert werden:

```python
from pydantic import BaseModel
from dspy.functional import TypedPredictor

class CriterionAnalysis(BaseModel):
    status: Literal["erfüllt", "nicht erfüllt", "teilweise erfüllt"]
    quote: str
    analysis: str

# Würde automatisch verschiedene Parsing-Strategien versuchen
analyzer = TypedPredictor(output_type=CriterionAnalysis)
```

Diese Option bleibt als Fallback für spätere Iterationen, wenn sich die LLM-Fähigkeiten verbessern.

## 10. Spätere Ideen
- Spezifische Prompts für unterschiedliche Aufgabentypen
- Möglichkeit, Feed-Up generieren zu lassen
- Feed-Back und Feed-Forward in verschiedenfarbigen Boxen darstellen
- Optimierung in DSPy
- Gewichtung von Bewertungskriterien (z.B. Hauptkriterium 40%, Nebenkriterien je 20%)
- Migration zu TypedPredictor wenn LLMs besser werden
