# Claude Prompt: Wissensfestiger Endlos-Wiederholung Problem

## Kontext & Aufgabe

Du bist ein Senior Software Engineer mit Expertise in Streamlit, Python Session Management und Web-UI Debugging. Analysiere ein kritisches Problem in unserem Spaced-Repetition Lernsystem und entwickle konkrete Lösungsstrategien.

## Problem Statement

**KRITISCH:** Unser Wissensfestiger-System ist in einer Endlos-Schleife gefangen. Nach jeder Feedback-Anzeige wird wieder dieselbe Aufgabe angezeigt, anstatt zur nächsten fälligen Aufgabe zu wechseln. Das macht das gesamte Spaced-Repetition-System unbrauchbar.

## System-Architektur Überblick

**Tech Stack:**
- **Frontend:** Streamlit (Python-basierte Web-UI)
- **Backend:** Supabase (PostgreSQL + RLS)
- **AI Processing:** Asynchroner Background Worker (feedback_worker.py)
- **Session Management:** Streamlit Session State + Custom MasterySessionState Class

**Datenfluss:**
1. User reicht Aufgabe ein → `create_submission()` 
2. Background Worker generiert AI-Feedback → `student_mastery_progress` Update
3. UI zeigt Feedback → "Nächste Aufgabe" Button 
4. **PROBLEM:** Button-Click führt nicht zur nächsten Task

## Code-Analyse Anfrage

Analysiere diese Dateien systematisch und identifiziere die Root Causes:

### 1. Haupt-UI Logic
**Datei:** `/app/pages/7_Wissensfestiger.py`
- **Fokus:** Zeilen 78-120 (Task Loading Logic)
- **Fokus:** Zeilen 172-241 (Feedback Display & Button Logic)
- **Kritische Funktion:** `get_next_mastery_task_or_unviewed_feedback()` Call
- **Problem:** `st.button("Nächste Aufgabe →")` Click wird nicht verarbeitet

### 2. Session State Management
**Datei:** `/app/utils/mastery_state.py`
- **Fokus:** `MasterySessionState` class
- **Kritische Methoden:** `clear_task()`, `get_course_state()`, `set_task()`
- **Problem:** Tasks werden nicht aus Session State entfernt

### 3. Database Query Logic
**Datei:** `/app/utils/db_queries.py`  
- **Fokus:** Zeilen 2188-2229 (`get_next_mastery_task_or_unviewed_feedback`)
- **Fokus:** Zeilen 2118-2181 (`get_next_due_mastery_task`)
- **Problem:** Ungelesene Feedbacks akkumulieren sich, `show_feedback` wird immer getriggert

### 4. Worker Integration
**Datei:** `/app/workers/worker_ai.py`
- **Fokus:** Zeilen 233-248 (Mastery Progress Update)
- **Status:** FUNKTIONIERT (kürzlich gefixt)

### 5. Issue-Dokumentation
**Referenz:** `/docs/issues/wissensfestiger_endlos_wiederholung.md`
- **Alle bisherigen Debug-Erkenntnisse**
- **Fehlgeschlagene Lösungsansätze**

## Spezifische Analyse-Fragen

### 1. Streamlit Button Behavior
**Frage:** Warum werden Button-Clicks in diesem Kontext nicht registriert?
- Ist es ein Streamlit Rerun-Timing Problem?
- Interferiert der `answer_submitted` State mit Button-Handling?
- Gibt es Session-State-Konflikte die Button-Events blockieren?

### 2. Session State Architecture
**Frage:** Warum schlägt `MasterySessionState.clear_task()` fehl?
- Sind die Dictionary-Updates korrekt implementiert?
- Gibt es Race Conditions zwischen Session State Read/Write?
- Interferiert der kurs-spezifische State-Container?

### 3. Database State vs. Session State Synchronization
**Frage:** Warum akkumulieren sich ungelesene Feedbacks?
- Werden SQL-Updates überhaupt ausgeführt?
- Ist die `feedback_viewed_at` Update-Logic korrekt?
- Gibt es Transaktions-/Rollback-Probleme?

### 4. Task Selection Algorithm
**Frage:** Warum gibt `get_next_mastery_task_or_unviewed_feedback` immer `show_feedback` zurück?
- Ist die Prioritäts-Logic korrekt (ungelesen vs. fällig)?
- Funktioniert die kurs-spezifische Filterung?
- Werden die Joins korrekt ausgeführt?

## Erwartete Deliverables

### 1. Root Cause Analysis
- **Primäre Ursache:** Das Haupt-Problem identifizieren
- **Sekundäre Ursachen:** Beitragende Faktoren
- **Interaction Effects:** Wie die Probleme sich verstärken

### 2. Konkrete Lösungsstrategien
Für jeden identifizierten Root Cause:
- **Option A:** Minimal-invasive Fix (wenn möglich)
- **Option B:** Architektur-Change (wenn nötig)
- **Option C:** Komplett neuer Ansatz (wenn erforderlich)

### 3. Implementierung-Roadmap
- **Sofort:** Quick-Wins die das Problem teilweise beheben
- **Kurzfristig:** Solide Lösungen (1-2 Tage Aufwand)
- **Langfristig:** Architekturelle Verbesserungen

### 4. Code-Patches
Für die wahrscheinlichste Lösung:
- Konkrete Code-Änderungen
- Testing-Strategie
- Rollback-Plan

## Debug-Evidenz

**Session State Problem:**
```python
# Diese Bedingung wird nie False:
if not course_state['answer_submitted'] and not course_state['current_task']:
    # Task Loading Logic - wird nie erreicht
```

**Button Problem:**
```python
# Diese Debug-Ausgaben erscheinen nie:
if st.button("Nächste Aufgabe →"):
    st.write("DEBUG: Button was clicked!")  # ← Nie ausgeführt
```

**Database Evidence:**
```sql
-- Viele ungelesene Submissions akkumulieren:
SELECT COUNT(*) FROM submission 
WHERE feedback_status = 'completed' 
AND feedback_viewed_at IS NULL 
AND task_id = 'b915c55e-9d06-48ae-8b59-ffd65e20bb16';
-- Result: 15+ ungelesene Feedbacks
```

## Constraints & Anforderungen

**Muss beibehalten werden:**
- Feedback-Persistierung (User können Seite während Worker-Verarbeitung verlassen)
- Kurs-spezifische Session States
- Spaced-Repetition-Algorithmus
- Asynchrone AI-Verarbeitung

**Darf verändert werden:**
- Button-Implementation
- Session State Struktur
- Database State Management
- UI-Flow

## Erwartete Analyse-Tiefe

- **Code-Level:** Zeile-für-Zeile Analyse der kritischen Pfade
- **Architecture-Level:** System-Interaktionen und State-Management
- **Framework-Level:** Streamlit-spezifische Eigenarten und Limitationen
- **Database-Level:** Query-Performance und Transaktions-Verhalten

Führe eine forensische Code-Analyse durch und entwickle eine klare, implementierbare Lösung für dieses kritische Problem.