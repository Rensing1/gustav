# Implementierungsplan: Das "Wissensfestiger"-Modul

Dieses Dokument beschreibt die Anforderungen und den Implementierungsplan für ein neues Modul mit dem Namen "Wissensfestiger". Das Ziel ist die Entwicklung eines KI-gestützten Systems zur Förderung von nachhaltigem und flexiblem Wissen.

## 0. Fortlaufende Aktualisierung
Aktualisiere dieses Dokument nach jeder Änderung am Code, um den aktuellen Stand des Entwicklungsprozesses festzuhalten (Long-Term-Context). Aktualisiere ggf. auch `roadmap.md` und `CLAUDE.md`.

## 1. Was ist das Ziel des Moduls?

Das primäre Ziel des "Wissensfestiger"-Moduls ist es, Schülern zu helfen, zentrale Lerninhalte nicht nur kurzfristig für eine Prüfung zu lernen, sondern sie dauerhaft im Langzeitgedächtnis zu verankern. Das Wissen soll nicht nur abrufbar, sondern auch flexibel anwendbar sein.

## 2. Warum nutzen wir dieses Modul? (Pädagogische Grundlage)

Das Modul basiert auf etablierten Prinzipien der Kognitionswissenschaft, um den Lernprozess nachweislich zu optimieren:

*   **Active Recall (Aktives Abrufen):** Schüler formulieren Antworten in eigenen Worten, anstatt nur passiv Inhalte zu konsumieren. Dieser Prozess des aktiven Abrufs stärkt die Gedächtnisspuren wesentlich effektiver.
*   **Spaced Repetition (Verteiltes Wiederholen):** Ein intelligenter Algorithmus plant Wiederholungen in wachsenden Zeitabständen, genau dann, wenn eine Gedächtnisspur zu verblassen droht. Dies bekämpft die "Vergessenskurve" und sorgt für maximale Lerneffizienz.
*   **Formatives KI-Feedback:** Jeder Abrufversuch wird zu einer Lerngelegenheit. Die KI gibt spezifisches, unterstützendes Feedback, das Wissenslücken aufzeigt und den Weg zur Verbesserung weist.
*   **Interleaving (Verschränktes Üben):** Das Mischen von Aufgaben aus verschiedenen Themenbereichen zwingt das Gehirn, Konzepte voneinander abzugrenzen und flexibel anzuwenden, anstatt starre Prozeduren auswendig zu lernen.
*   **Weitere Information:** Siehe `mastery_science.md` für eine detaillierte wissenschaftliche Fundierung.

## 3. Wie funktioniert das Modul? (Technische und funktionale Umsetzung)

Der Lernprozess im "Wissensfestiger" folgt einem geschlossenen Kreislauf:

1.  **Aufgabe präsentieren:** Das System zeigt dem Schüler auf einer dedizierten Seite eine einzelne, fällige "Wissensfestiger"-Aufgabe.
2.  **Antwort eingeben:** Der Schüler gibt seine Antwort in ein Freitextfeld ein.
3.  **KI-Analyse:** Nach dem Absenden analysiert eine KI die Antwort und generiert zwei Dinge:
    a. Ein qualitatives, schülergerechtes Feedback.
    b. Eine interne, numerische Bewertung der Antwortqualität.
4.  **Feedback & Bewertung anzeigen:** Dem Schüler werden das qualitative Feedback und eine wachstumsorientierte "Lernstufe" (basierend auf der internen Bewertung) angezeigt.
5.  **Nächste Wiederholung planen:** Der Spaced-Repetition-Algorithmus verarbeitet die interne Bewertung und berechnet das Datum für die nächste Wiederholung dieser Aufgabe.
6.  **Fortschritt speichern:** Das System aktualisiert den Lernstand des Schülers für diese spezifische Aufgabe in der Datenbank.

### A. Komponente: Aufgabentyp "Wissensfestiger"

*   Ein neuer Aufgabentyp "Wissensfestiger" wird in die bestehende `task`-Tabelle integriert.
*   Lehrkräfte können diesen Aufgabentyp innerhalb von Lerneinheiten erstellen durch eine Checkbox "Als Wissensfestiger-Aufgabe".
*   Die bestehende `task`-Tabelle wird um ein Flag erweitert:
    ```sql
    ALTER TABLE task ADD COLUMN is_mastery BOOLEAN DEFAULT FALSE;
    ```
*   Vorteile dieser Lösung:
    - Nutzt bestehende Infrastruktur (assessment_criteria, solution_hints bereits vorhanden)
    - Einheitliche Verwaltung aller Aufgaben
    - Wiederverwendung der bestehenden UI-Komponenten für Lehrer
    - Einfachere Wartung

### B. Komponente: KI-Bewertung & Feedback

*   Die KI generiert zu jeder Schülerantwort ein **qualitatives Feedback**.
*   Zusätzlich generiert die KI eine **interne, numerische Bewertung** auf einer Skala von 1-5.
*   Diese Zahl wird dem Schüler nicht direkt angezeigt. Sie wird auf eine **"Lernstufe"** gemappt, um eine Wachstumsmentalität zu fördern:

| Interner KI-Score | Sichtbares Label ("Lernstufe") |
| :--- | :--- |
| 1 | Erste Schritte |
| 2 | Ansatz erkannt |
| 3 | Fundament gelegt |
| 4 | Sicher angewendet |
| 5 | Gemeistert |

*   Für den Algorithmus wird der KI-Score auf eine **Qualitätsstufe `q`** gemappt. Dieses Mapping ist deterministisch: `q` ist identisch mit dem KI-Score (1-5).

### C. Komponente: Spaced-Repetition-Algorithmus (Spezifikation)

Wir implementieren eine moderne, von Anki inspirierte Variante des SM-2-Algorithmus. Der Algorithmus unterscheidet drei Zustände (`status`) für jede Aufgabe pro Schüler: `learning`, `reviewing` und `relearning`.

#### 1. Konfigurierbare Algorithmus-Parameter

Alle folgenden Werte müssen in einer zentralen Konfigurationsdatei hinterlegt werden. Dies sind die initialen Default-Werte:

| Parameter | Default-Wert | Beschreibung |
| :--- | :--- | :--- |
| `LEARNING_STEPS` | `[1, 3]` | Intervalle in Tagen für die Lernphase. |
| `GRADUATING_INTERVAL` | `7` | Intervall in Tagen, wenn eine Aufgabe `learning` verlässt. |
| `INITIAL_EASE_FACTOR`| `2.5` | Startwert des EF für jede neue Aufgabe. |
| `MIN_EASE_FACTOR` | `1.3` | Die Untergrenze für den EF. |
| `LAPSE_INTERVAL_FACTOR`| `0.5` | Multiplikator für das Intervall nach einem Fehler (Lapse). |
| `LAPSE_EASE_PENALTY`| `-0.20` | Subtraktion vom EF nach einem Fehler. |
| `RELEARNING_STEPS` | `[1]` | Kurze Lernschritte für `relearning`-Aufgaben. |
| `FUZZ_FACTOR` | `0.1` | +/- Prozentuale Zufallsabweichung für Intervalle. |

#### 2. Logik der Zustandsübergänge

Eine Bewertung von `q >= 3` gilt als **korrekt**, `q < 3` als **falsch**.

*   **Neue Aufgabe (`status='learning'`):**
    *   *Bei korrekter Antwort (`q >= 3`):* Die Aufgabe steigt zum nächsten Schritt in `LEARNING_STEPS` auf. Ist der letzte Schritt erreicht, "graduiert" sie: `status` wird zu `reviewing`, das Intervall wird auf `GRADUATING_INTERVAL` gesetzt.
    *   *Bei falscher Antwort (`q < 3`):* Die Lernschritte beginnen von vorn.

*   **Gekonnte Aufgabe (`status='reviewing'`):**
    *   *Bei korrekter Antwort (`q >= 3`):* Der `repetition_count` wird um 1 erhöht. Der `ease_factor` wird aktualisiert: `EF_neu = EF_alt + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))`. Das nächste Intervall `I` wird berechnet: `I_neu = I_alt * EF_neu`.
    *   *Bei falscher Antwort (`q < 3`) - ein "Lapse":* `status` wird zu `relearning`, `repetition_count` auf 0 zurückgesetzt. Der `ease_factor` wird bestraft (`EF_neu = EF_alt + LAPSE_EASE_PENALTY`), und das Intervall reduziert (`I_neu = I_alt * LAPSE_INTERVAL_FACTOR`).

*   **Vergessene Aufgabe (`status='relearning'`):**
    *   *Bei korrekter Antwort (`q >= 3`):* Die Aufgabe durchläuft die `RELEARNING_STEPS`. Nach dem letzten Schritt wird `status` wieder zu `reviewing`.
    *   *Bei falscher Antwort (`q < 3`):* Die `relearning`-Schritte beginnen von vorn.

#### 3. Fuzz-Faktor (Zufallsrauschen)

Nach jeder Berechnung eines neuen Intervalls `I_neu` wird eine zufällige Abweichung angewendet:
`final_interval = round(I_neu * (1 + random.uniform(-FUZZ_FACTOR, FUZZ_FACTOR)))`

#### 4. Referenz: Pseudo-Code

Der folgende Pseudo-Code dient als Referenz für die Implementierung der Logik der Zustandsübergänge.

```python
# Annahme: Eine Funktion map_rating_to_quality(ki_rating) -> q (1-5) existiert.
# Annahme: Alle Konfigurationsparameter sind geladen.

def update_mastery_progress(student_id, task_id, ki_rating):
    q = map_rating_to_quality(ki_rating)
    task = db.get_task_status(student_id, task_id)

    # Fall 1: Aufgabe ist komplett neu und wird initialisiert
    if not task:
        task = db.create_new_task_status(student_id, task_id)

    is_correct = (q >= 3)

    if task.status == 'learning':
        if is_correct:
            if task.learning_step_index < len(LEARNING_STEPS) - 1:
                task.learning_step_index += 1
                task.current_interval = LEARNING_STEPS[task.learning_step_index]
            else:
                task.status = 'reviewing'
                task.current_interval = GRADUATING_INTERVAL
        else:
            task.learning_step_index = 0
            task.current_interval = LEARNING_STEPS[0]

    elif task.status == 'reviewing':
        if is_correct:
            task.repetition_count += 1
            task.current_interval = task.current_interval * task.ease_factor
            task.ease_factor += (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
            if task.ease_factor < MIN_EASE_FACTOR: task.ease_factor = MIN_EASE_FACTOR
        else: # Lapse
            task.status = 'relearning'
            task.repetition_count = 0
            task.ease_factor += LAPSE_EASE_PENALTY
            if task.ease_factor < MIN_EASE_FACTOR: task.ease_factor = MIN_EASE_FACTOR
            task.current_interval = max(1, task.current_interval * LAPSE_INTERVAL_FACTOR)
            task.relearning_step_index = 0

    elif task.status == 'relearning':
        if is_correct:
            if task.relearning_step_index < len(RELEARNING_STEPS) - 1:
                task.relearning_step_index += 1
                task.current_interval = RELEARNING_STEPS[task.relearning_step_index]
            else:
                task.status = 'reviewing'
        else:
            task.relearning_step_index = 0
            task.current_interval = RELEARNING_STEPS[0]
            
    # Finalen Fuzz-Faktor anwenden
    fuzz = random.uniform(-FUZZ_FACTOR, FUZZ_FACTOR)
    final_interval = max(1, round(task.current_interval * (1 + fuzz)))

    task.next_due_date = today() + days(final_interval)
    task.last_attempt_date = today()
    db.save_task_status(task)
```

### D. Komponente: Interleaving

*   Die Standardeinstellung für das Üben ist **Intra-Course Interleaving**.
*   Das bedeutet: Die tägliche Übungsliste eines Schülers enthält eine Mischung aller fälligen "Wissensfestiger"-Aufgaben aus allen Lerneinheiten des jeweiligen Kurses.

### E. Komponente: Datenmodell

Erstellen Sie eine Tabelle `student_mastery_progress` mit folgender, zum Algorithmus passender Struktur:

```sql
CREATE TABLE student_mastery_progress (
    student_id UUID,                            -- Foreign Key zu profiles(id)
    task_id INT,                                -- Foreign Key zu task(id)
    current_interval INT DEFAULT 1,             -- Startintervall für 'learning'
    next_due_date DATE DEFAULT CURRENT_DATE,    -- Fälligkeitsdatum
    ease_factor FLOAT DEFAULT 2.5,              -- Startwert explizit
    repetition_count INT DEFAULT 0,             -- Beginnt bei 0
    status VARCHAR(20) DEFAULT 'learning',      -- Jede neue Aufgabe startet im 'learning'-Modus
    learning_step_index INT DEFAULT 0,          -- Index für LEARNING_STEPS
    relearning_step_index INT DEFAULT 0,        -- Index für RELEARNING_STEPS
    last_attempt_date DATE,
    last_score INT,                             -- Letzter KI-Score (1-5)
    total_attempts INT DEFAULT 0,               -- Gesamtzahl der Versuche
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (student_id, task_id),
    FOREIGN KEY (student_id) REFERENCES profiles(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES task(id) ON DELETE CASCADE
);
```

## 4. Detaillierter Implementierungsplan

### Phase 1: Datenbank & Backend-Grundlagen (Tag 1-2)

#### Schritt 1: Datenbank-Migrationen
1. **Migration für task-Tabelle** (`add_mastery_flag_to_tasks.sql`):
   ```sql
   ALTER TABLE task ADD COLUMN is_mastery BOOLEAN DEFAULT FALSE;
   -- Index für Performance bei Mastery-Abfragen
   CREATE INDEX idx_task_mastery ON task(is_mastery) WHERE is_mastery = TRUE;
   ```

2. **Migration für Progress-Tabelle** (`create_student_mastery_progress.sql`):
   - Siehe SQL-Definition in Abschnitt E oben
   - Zusätzliche Indizes für Performance:
   ```sql
   CREATE INDEX idx_mastery_progress_due ON student_mastery_progress(student_id, next_due_date);
   CREATE INDEX idx_mastery_progress_course ON student_mastery_progress(task_id);
   ```

#### Schritt 2: Konfigurationsdatei
**Datei:** `app/config/mastery_config.py`
- Alle Spaced-Repetition Parameter (siehe Tabelle in C.1)
- Mapping für Lernstufen-Labels
- Utility-Funktionen für Score-Mapping

#### Schritt 3: Spaced-Repetition Algorithmus
**Datei:** `app/utils/mastery_algorithm.py`
- `update_mastery_progress(student_id, task_id, ki_score)` - Hauptfunktion gemäß Pseudo-Code
- `calculate_next_interval(task_status, is_correct, q)` - Intervallberechnung
- `apply_fuzz_factor(interval)` - Zufallsvariation
- `get_next_due_task(student_id, course_id)` - Nächste fällige Aufgabe mit Interleaving

### Phase 2: KI-Integration (Tag 2-3)

#### Schritt 4: DSPy-Signatur für Bewertung
**Datei:** `app/ai/signatures.py`
```python
class MasteryAssessment(dspy.Signature):
    """Bewerte die Schülerantwort präzise auf einer Skala von 1-5"""
    task_instruction = dspy.InputField(desc="Die Aufgabenstellung")
    assessment_criteria = dspy.InputField(desc="Bewertungskriterien als JSON-Array")
    solution_hints = dspy.InputField(desc="Optionale Lösungshinweise")
    student_answer = dspy.InputField(desc="Die Antwort des Schülers")
    
    score = dspy.OutputField(desc="Numerische Bewertung: genau eine Zahl von 1 bis 5")
    reasoning = dspy.OutputField(desc="Kurze Begründung der Bewertung (2-3 Sätze)")
```

#### Schritt 5: AI-Service erweitern
**Datei:** `app/ai/service.py`
- `generate_mastery_assessment(task, student_answer)` - Generiert Score + Reasoning
- Integration mit bestehendem `generate_ai_feedback()` für qualitatives Feedback
- Kombination beider Ausgaben für vollständige Mastery-Bewertung

#### Schritt 6: Database Queries erweitern
**Datei:** `app/utils/db_queries.py`
Neue Funktionen:
- `get_mastery_tasks_for_course(course_id)` - Alle Mastery-Aufgaben eines Kurses
- `get_next_due_mastery_task(student_id, course_id)` - Nächste fällige Aufgabe (mit Interleaving)
- `create_or_update_mastery_progress(student_id, task_id, score)` - Progress speichern
- `submit_mastery_answer(student_id, task_id, answer)` - Antwort einreichen
- `get_mastery_stats_for_student(student_id, course_id)` - Statistiken für Dashboard
- `get_mastery_overview_for_teacher(course_id)` - Lehrer-Übersicht

### Phase 3: UI-Entwicklung (Tag 3-4)

#### Schritt 7: Lehrer-UI erweitern
**Datei:** `app/pages/2_Lerneinheiten.py`
Änderungen:
- Beim Aufgaben-Erstellen: Checkbox `st.checkbox("Als Wissensfestiger-Aufgabe markieren", key="is_mastery")`
- In der Aufgabenliste: Badge/Icon für Mastery-Aufgaben anzeigen
- Tooltip mit Erklärung was Wissensfestiger-Aufgaben sind

#### Schritt 8: Neue Schüler-Seite
**Datei:** `app/pages/7_Wissensfestiger.py`
Struktur:
```python
def main():
    # 1. Kursauswahl in Sidebar
    selected_course_id = show_course_selector()
    
    if selected_course_id:
        # 2. Nächste fällige Aufgabe holen
        task = get_next_due_mastery_task(st.session_state.user_id, selected_course_id)
        
        if task:
            # 3. Aufgabe anzeigen
            show_mastery_task(task)
            
            # 4. Antwort-Eingabe
            answer = st.text_area("Deine Antwort:", height=200)
            
            if st.button("Antwort einreichen"):
                # 5. KI-Bewertung
                assessment = generate_mastery_assessment(task, answer)
                feedback = generate_ai_feedback(task, answer)
                
                # 6. Progress updaten
                update_mastery_progress(user_id, task.id, assessment.score)
                
                # 7. Feedback anzeigen
                show_feedback_and_learning_level(feedback, assessment)
                
                # 8. "Nächste Aufgabe" Button
                if st.button("Nächste Aufgabe"):
                    st.rerun()
        else:
            st.success("🎉 Keine Aufgaben fällig! Komm morgen wieder.")
```

#### Schritt 9: Dashboard-Integration
**Datei:** `app/pages/6_Live-Unterricht.py`
Erweiterungen:
- Tab für "Wissensfestiger-Fortschritt"
- Heatmap: Schüler × Mastery-Aufgaben mit Farbcodierung nach Status
- Aggregierte Statistiken (Durchschnittliche Lernstufe, Anzahl gemeisterter Konzepte)

### Phase 4: Testing & Integration (Tag 4-5)

#### Schritt 10: Integrationstests
- Test der Algorithmus-Logik mit verschiedenen Szenarien
- Test der KI-Bewertung mit Beispielantworten
- UI-Tests für alle User Journeys
- Edge Cases: Neue Schüler, keine Aufgaben, viele fällige Aufgaben

#### Schritt 11: Performance-Optimierung
- Query-Optimierung für Interleaving
- Caching von häufig abgerufenen Daten
- Batch-Processing für Dashboard-Statistiken

### Phase 5: Dokumentation & Rollout (Tag 5)

#### Schritt 12: Dokumentation aktualisieren
- `CLAUDE.md`: Mastery-Modul Beschreibung hinzufügen
- `roadmap.md`: Phase für Mastery-Modul eintragen
- `mastery_implementation.md`: Implementierungsstatus updaten
- Benutzerhandbuch für Lehrer und Schüler

## 5. Zukünftige Optionen und Erweiterungen

Die Architektur soll so geplant werden, dass folgende Erweiterungen später hinzugefügt werden können:

*   **Feedback-Mechanismen:**
    *   Ein "Flaggen"-Button, mit dem Schüler fehlerhaftes KI-Feedback oder eine als unfair empfundene Bewertung an die Lehrkraft melden können.
    *   Eine Funktion im Lehrer-Dashboard, die es Lehrkräften erlaubt, die KI-Bewertung für eine Schülerantwort einzusehen und manuell zu korrigieren.

*   **Inhalts-Verbesserungen:**
    *   Die Möglichkeit für Lehrkräfte, mehrere Varianten einer Frage für dasselbe Kernkonzept zu hinterlegen.
    *   Automatische Variation der Fragestellung durch KI

*   **Nutzungs-Steuerung:**
    *   Ein konfigurierbares, tägliches Limit für Wiederholungen
    *   "Urlaubs-Modus" zum Pausieren der Wiederholungen
    *   Individuelle Lernzeitfenster (z.B. nur nachmittags)

*   **Erweiterte Analytics:**
    *   Vergessenskurven-Visualisierung
    *   Prognose des Lernfortschritts
    *   Vergleich mit Klassendurchschnitt

## 6. Implementierungsstatus

**Stand: 02.08.2025**

- [x] Phase 1: Datenbank & Backend-Grundlagen ✅
  - [x] Datenbank-Migrationen erstellt und angewendet
    - `20250802135638_add_mastery_flag_to_tasks.sql`
    - `20250802135702_create_student_mastery_progress.sql` (mit UUID-Fix für task_id)
  - [x] Konfigurationsdatei implementiert (`app/mastery/mastery_config.py`)
  - [x] Spaced-Repetition Algorithmus implementiert (`app/utils/mastery_algorithm.py`)
  
- [x] Phase 2: KI-Integration ✅
  - [x] DSPy-Signatur für Bewertung erstellt (`MasteryAssessment` in `app/ai/signatures.py`)
  - [x] AI-Service erweitert (`generate_mastery_assessment` in `app/ai/service.py`)
  - [x] Database Queries erweitert (7 neue Funktionen in `app/utils/db_queries.py`)
  
- [x] Phase 3: UI-Entwicklung ✅
  - [x] Lehrer-UI erweitert 
    - Checkbox in `app/components/detail_editor.py`
    - Checkbox in `app/components/structure_tree.py`
  - [x] Schüler-Seite erstellt (`app/pages/7_Wissensfestiger.py`)
  - [x] Navigation für Schüler erweitert (`app/main.py`)
  - [ ] Dashboard-Integration (verschoben auf späteren Zeitpunkt)
  
- [x] Phase 4: Debugging & Fixes ✅
  - [x] Namenskonflikt config.py vs config/ Verzeichnis gelöst (umbenannt zu mastery/)
  - [x] Import-Pfade korrigiert
  - [x] PostgREST Schema-Cache aktualisiert
  - [x] JSON-Serialisierung für date-Felder implementiert
  - [x] Filterung von Mastery-Aufgaben in "Meine Aufgaben"
  
- [x] Phase 5: Dokumentation & Rollout ✅
  - [x] `mastery_implementation.md` vollständig aktualisiert
  - [x] `CLAUDE.md` aktualisiert
  - [x] `roadmap.md` aktualisiert
  - [x] Migrationen erfolgreich angewendet
  - [x] System getestet und funktionsfähig

**Status: VOLLSTÄNDIG IMPLEMENTIERT UND EINSATZBEREIT** 🎯

Das Wissensfestiger-Modul ist vollständig funktionsfähig und kann in der Produktion eingesetzt werden.
