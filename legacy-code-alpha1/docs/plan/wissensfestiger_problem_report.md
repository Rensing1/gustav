# 🔍 Umfassender Problem-Report: Wissensfestiger zeigt falsche Aufgabe

## Executive Summary

Der Wissensfestiger zeigt wiederholt die gleiche Aufgabe ("Oder-Gatter erklären") an, obwohl andere Aufgaben eine höhere Priorität haben sollten. Die Ursache ist ein **kritischer Import-Konflikt**: Es existieren zwei konkurrierende Implementierungen von `get_next_mastery_task_or_unviewed_feedback`, wobei die veraltete Version verwendet wird, die die neue RPC-Logik komplett ignoriert.

## 🎯 Kernproblem

### 1. **Doppelte Implementierung (HAUPTURSACHE)**

```python
# ALTE Version in db_queries.py (Zeile 1564-1608)
def get_next_mastery_task_or_unviewed_feedback(student_id: str, course_id: str) -> dict:
    # IGNORIERT die RPC-Funktion komplett!
    # Ruft nur get_next_due_mastery_task auf
    next_task, error = get_next_due_mastery_task(student_id, course_id)
    return {
        'type': 'new_task',
        'task': next_task,
        'error': error
    }

# NEUE Version in db/learning/mastery.py (Zeile 115-235) 
def get_next_mastery_task_or_unviewed_feedback(student_id: str, course_id: str) -> dict:
    # Nutzt korrekt die RPC-Funktion
    client.rpc('get_next_mastery_task_or_unviewed_feedback', {...})
```

Der Import in `7_Wissensfestiger.py` lädt die ALTE Version:
```python
from utils.db_queries import get_next_mastery_task_or_unviewed_feedback  # ❌ Alte Version!
```

### 2. **Aggressive Session State Bereinigung**

In `7_Wissensfestiger.py` (Zeile 87-93):
```python
if current_task and not course_state.get('answer_submitted', False):
    # Immer neue Task laden wenn keine Antwort submitted ist
    print(f"🔄 Clearing current task to load fresh due task")
    MasterySessionState.clear_task(selected_course_id, keep_feedback_context=False)
```

Dies löscht bei JEDEM Page-Reload die aktuelle Aufgabe, auch wenn sie korrekt ist.

## 📊 Beweisführung

### SQL-Analyse der Prioritäten

```sql
-- User: test1@test.de (de70c0c4-f095-47d6-a35a-dbec3f1f8cd4)
-- Kurs: Informatik

-- Erwartete Prioritäten laut RPC-Funktion:
-- 1. Unbearbeitete Aufgaben: Priorität 1000
-- 2. Überfällige Aufgaben: Priorität 500+
-- 3. Oder-Gatter (fällig am 13.09): Priorität ~98

-- Die RPC-Funktion würde korrekt priorisieren,
-- wird aber nie aufgerufen!
```

### Import-Kette

1. `7_Wissensfestiger.py` importiert aus `utils.db_queries`
2. `db_queries.py` hat BEIDE:
   - Import der neuen Version: `from .db.learning.mastery import get_next_mastery_task_or_unviewed_feedback`
   - Eigene alte Implementierung mit gleicher Signatur (überschreibt den Import!)
3. Python verwendet die lokale Definition statt des Imports

## 🔧 Lösungsoptionen

### Option 1: **Sofortlösung - Alte Implementierung entfernen** ✅ EMPFOHLEN

```python
# In db_queries.py:
# 1. ENTFERNE die alte Implementierung (Zeile 1564-1608)
# 2. Der Import aus .db.learning.mastery bleibt bestehen
# 3. Keine weiteren Änderungen nötig!
```

**Vorteile:**
- Minimaler Eingriff
- Sofort wirksam
- Keine Breaking Changes

**Nachteile:**
- Keine

### Option 2: **Import in Wissensfestiger korrigieren**

```python
# In 7_Wissensfestiger.py:
from utils.db.learning.mastery import get_next_mastery_task_or_unviewed_feedback
```

**Vorteile:**
- Expliziter Import
- Klarere Abhängigkeiten

**Nachteile:**
- Andere Module könnten auch betroffen sein
- Inkonsistente Import-Struktur

### Option 3: **Session State Logik verbessern**

```python
# In 7_Wissensfestiger.py, Zeile 87-93 ersetzen durch:
if current_task and not course_state.get('answer_submitted', False):
    # Prüfe ob Task noch gültig ist
    task_id = current_task.get('id')
    if task_id:
        # Validiere über RPC ob Task noch die höchste Priorität hat
        new_task_data = get_next_mastery_task_or_unviewed_feedback(student_id, selected_course_id)
        if new_task_data.get('task', {}).get('id') != task_id:
            # Nur löschen wenn wirklich eine andere Task Priorität hat
            MasterySessionState.clear_task(selected_course_id, keep_feedback_context=False)
```

**Vorteile:**
- Intelligentere State-Verwaltung
- Weniger unnötige Reloads

**Nachteile:**
- Zusätzliche DB-Abfrage
- Löst nicht das Hauptproblem

## 🚀 Empfohlene Schritte

### 1. **SOFORT: Hauptproblem beheben**
```bash
# Option 1 implementieren
# Entferne Zeilen 1564-1608 aus db_queries.py
```

### 2. **KURZFRISTIG: Tests hinzufügen**
```python
# Test dass die richtige Funktion aufgerufen wird
def test_correct_mastery_function_import():
    from utils.db_queries import get_next_mastery_task_or_unviewed_feedback
    from utils.db.learning.mastery import get_next_mastery_task_or_unviewed_feedback as correct_func
    assert get_next_mastery_task_or_unviewed_feedback is correct_func
```

### 3. **MITTELFRISTIG: Import-Struktur bereinigen**
- Überprüfe alle Module auf ähnliche Konflikte
- Etabliere klare Import-Konventionen
- Dokumentiere in CODESTYLE.md

## 🔍 Weitere Erkenntnisse

1. **Feedback-Logik deaktiviert**: Die alte Implementierung hat die Feedback-Prüfung komplett auskommentiert
2. **Keine Unit-Tests**: Solche Import-Konflikte wären durch Tests aufgefallen
3. **Inkonsistente Namensgebung**: `next_due_date` vs `next_review_date` in verschiedenen Teilen

## ✅ Erfolgskriterien

Nach der Implementierung sollte:
1. Die Aufgabe mit höchster Priorität angezeigt werden
2. Unbearbeitete Aufgaben Vorrang haben
3. Überfällige Aufgaben vor zukünftigen kommen
4. Session State nur bei echten Änderungen geleert werden

## 📝 Zusammenfassung

Das Problem ist eindeutig identifiziert und einfach zu beheben. Die alte Implementierung in `db_queries.py` muss entfernt werden, damit der korrekte Import aus `db.learning.mastery` verwendet wird. Dies ist eine **kritische Korrektur**, die sofort durchgeführt werden sollte.

---

*Report erstellt: 2025-09-11*
*Betroffene Dateien: db_queries.py (Zeile 1564-1608), 7_Wissensfestiger.py*