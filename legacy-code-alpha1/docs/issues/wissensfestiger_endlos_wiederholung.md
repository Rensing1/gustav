# Wissensfestiger: Endlos-Wiederholung der gleichen Aufgabe

## Problem

**Status:** KRITISCH - UNGELÖST  
**Erstellt:** 2025-08-25  
**Schwere:** Hoch - Wissensfestiger unbrauchbar

### Beschreibung

Der Wissensfestiger zeigt nach jeder Feedback-Anzeige wieder dieselbe Aufgabe an, anstatt zur nächsten fälligen Aufgabe zu wechseln. Dies führt zu einer Endlos-Schleife, die das gesamte Spaced-Repetition-System unbrauchbar macht.

### Symptome

1. **Endlos-Wiederholung:** Benutzer sehen immer dieselbe Task, egal wie oft sie diese beantwortet haben
2. **Feedback-Persistierung funktioniert:** Das ungelesene Feedback wird korrekt angezeigt 
3. **Mastery Progress Update funktioniert:** `next_due_date` wird korrekt in DB gesetzt
4. **Task-Auswahl-Algorithmus funktioniert:** `get_next_due_mastery_task` gibt korrekte andere Tasks zurück
5. **Session State bleibt "hängen":** Tasks werden nicht aus dem Session State entfernt

### Root Cause Analysis

Nach intensiver Debugging-Session am 2025-08-25 identifiziert:

#### 1. Design-Intention (funktioniert)
- **Feedback-Persistierung:** User können Seite während Worker-Verarbeitung verlassen und kehren zum fertigen Feedback zurück ✅
- **Show-Feedback-Priorität:** `get_next_mastery_task_or_unviewed_feedback` priorisiert ungelesenes Feedback über neue Tasks ✅

#### 2. Problem-Kette (kaputt)
1. **User reicht Antwort ein** → Worker generiert Feedback ✅
2. **Feedback wird angezeigt** (`show_feedback`) ✅  
3. **"Nächste Aufgabe" geklickt** → Soll alle Feedbacks als gelesen markieren ❌
4. **Session State bereinigen** → Soll current_task entfernen ❌
5. **Neue Task laden** → Soll nächste fällige Task anzeigen ❌

#### 3. Identifizierte Probleme

**A. Streamlit Button-System komplett defekt:**
- Buttons werden gerendert aber Clicks nicht registriert
- Keine Debug-Ausgaben nach Button-Clicks
- Auch alternative Button-Implementierungen (Session State Flags, Auto-Timer) funktionieren nicht

**B. Session State Cleanup schlägt fehl:**
- `MasterySessionState.clear_task()` entfernt Tasks nicht korrekt aus Session
- Direkte Session State Manipulation hat keinen Effekt
- Tasks bleiben im `course_state['current_task']` "hängen"

**C. Database Updates werden nicht ausgeführt:**
- SQL-Updates um Feedbacks als gelesen zu markieren werden nie ausgeführt
- Dadurch bleiben immer ungelesene Feedbacks bestehen
- `show_feedback` wird immer wieder getriggert

### Debug-Log Evidenz

```
# Erfolgreiche Teile:
DEBUG: feedback_status = completed ✅
DEBUG: task exists = True ✅  
DEBUG: task['id'] = b915c55e-9d06-48ae-8b59-ffd65e20bb16 ✅

# Fehlschlagende Teile:
DEBUG: 🔥 Button was clicked! ❌ (wird nie angezeigt)
DEBUG: Markiere Feedbacks als gelesen ❌ (wird nie erreicht)
DEBUG: State manually cleared ❌ (wird nie ausgeführt)
```

### Ungelöste Ansätze

1. **Standard Button:** `st.button()` - Click wird nicht registriert
2. **Button mit Key:** `st.button(key=...)` - Click wird nicht registriert  
3. **2-Phase Button:** Session Flag + Rerun - Flag wird nie gesetzt
4. **Auto-Timer System:** 5-Sekunden Timer - Timer wird nie ausgeführt
5. **Direkte Session Manipulation:** `st.session_state[key] = value` - Hat keinen Effekt
6. **MasterySessionState.clear_task():** Designed cleanup - Funktioniert nicht

### Technische Details

**Betroffene Dateien:**
- `/app/pages/7_Wissensfestiger.py` (Haupt-UI)
- `/app/utils/mastery_state.py` (Session State Management)  
- `/app/utils/db_queries.py` (get_next_mastery_task_or_unviewed_feedback)

**Database Evidenz:**
```sql
-- Viele ungelesene Feedbacks akkumulieren sich:
SELECT task_id, COUNT(*) FROM submission 
WHERE student_id = '...' 
AND feedback_status = 'completed' 
AND feedback_viewed_at IS NULL 
GROUP BY task_id;

-- Mastery Progress wird korrekt aktualisiert:
SELECT task_id, next_due_date FROM student_mastery_progress 
WHERE student_id = '...' 
ORDER BY last_reviewed_at DESC;
```

**Session State Struktur:**
```python
st.session_state.mastery_course_state = {
    'course_id': {
        'current_task': {...},  # ← Bleibt immer gesetzt
        'answer_submitted': True,  # ← Wird nie zurückgesetzt  
        'submission_id': '...',
        'last_answer': '...'
    }
}
```

### Auswirkungen

- **Wissensfestiger komplett unbrauchbar** 
- **Spaced Repetition funktioniert nicht**
- **User frustriert** durch endlose Wiederholung
- **Learning Analytics verfälscht** durch multiple Submissions der gleichen Task

### Nächste Schritte

**DRINGEND - Alternativer Ansatz erforderlich:**

1. **Complete Rewrite der Button-Logic** mit anderem Framework (z.B. custom JavaScript)
2. **Redesign der Session State Architektur** ohne Streamlit-Dependencies  
3. **Database-First Approach:** State in DB statt Session verwalten
4. **Vereinfachung der Feedback-Persistierung** zugunsten funktionierender Navigation

**Temporärer Workaround:**
- Wissensfestiger deaktivieren bis Problem gelöst
- Oder: Feedback-Persistierung entfernen und sofort zur nächsten Task wechseln

### Update 2025-08-25: Quick Fix implementiert

**Lösung:** Option A - Auto-Markierung von Feedback als gelesen

**Implementierte Änderungen:**
1. Feedback wird automatisch als "gelesen" markiert sobald es angezeigt wird (Zeile 189-196)
2. Button-Handler vereinfacht - nur noch Session State Clear ohne DB-Update (Zeile 248-251)
3. Warnhinweise hinzugefügt, dass Seite nicht verlassen werden soll (Zeile 147, 202)

**Trade-offs:**
- Verlust der Feedback-Persistierung (User können nicht mehr zu altem Feedback zurückkehren)
- Dafür: Wissensfestiger wieder funktionsfähig

**Status:** WORKAROUND AKTIV - Langfristige Lösung (Option C) sollte evaluiert werden

### Update 2025-08-25: Zusätzliches Problem identifiziert

**Neues Problem:** Trotz Auto-Markierung werden immer noch dieselben Aufgaben wiederholt

**Root Cause:**
1. **Zu wenige Aufgaben im Pool:** Nur 2 Mastery-Aufgaben im Kurs verfügbar
2. **Spaced Repetition funktioniert:** Nach Bearbeitung ist `next_due_date` = morgen
3. **Race Condition:** Auto-Markierung funktioniert nicht zuverlässig bei mehreren Streamlit Reruns
4. **Feedback-Priorität:** System zeigt immer ungelesenes Feedback vor neuen Aufgaben

**Temporäre Lösung:**
- Feedback-Persistierung komplett deaktiviert in `get_next_mastery_task_or_unviewed_feedback`
- Zeigt jetzt immer neue Aufgaben statt altes Feedback

**Empfehlungen:**
1. **Kurzfristig:** Mehr Mastery-Aufgaben zum Kurs hinzufügen (mindestens 10-15)
2. **Mittelfristig:** Button-Problem mit Custom JavaScript lösen
3. **Langfristig:** Database-driven State Management (Option C)

---

**Assignee:** Claude + Felix  
**Priority:** P0 - Kritisch  
**Estimate:** 1-2 Tage (Complete Rewrite erforderlich)