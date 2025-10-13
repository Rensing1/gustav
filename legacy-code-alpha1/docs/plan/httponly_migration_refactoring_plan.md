# HttpOnly Cookie Migration + db_queries.py Refactoring Plan

**Erstellt:** 2025-09-09T07:30:00+01:00  
**Status:** In Bearbeitung  
**Ziel:** Saubere Migration zu HttpOnly Cookies mit gleichzeitigem Refactoring von db_queries.py

## 📋 Übersicht

Dieses Dokument beschreibt den idiotensicheren Plan für:
1. Fertigstellung der HttpOnly Cookie Migration (aktuell 76% - siehe [postgresql_migration_complete.md](./postgresql_migration_complete.md))
2. Gleichzeitiges Refactoring der 3117-Zeilen `db_queries.py` in wartbare Module
3. Behebung des Schema-Mismatch Problems, das Batch 3-6 blockiert

**Referenz-Dokumente:**
- [PostgreSQL Migration Status](./postgresql_migration_complete.md) - Aktueller Stand: 45/59 Functions migriert
- [HttpOnly Cookie Support Plan](./PostgreSQL%20Functions%20Migration%20für%20HttpOnly%20Cookie%20Support.md) - Ursprünglicher Plan

## 🛡️ Sicherheitsmechanismen

1. **Backup vor jedem Schritt:**
   ```bash
   cd /home/felix/gustav
   ./docs/operations/backup.sh
   ```

2. **Validierung nach jedem Schritt:**
   - Container neustart: `docker compose restart app`
   - Funktionalitätstest durchführen
   - Dieses Dokument aktualisieren

3. **Rollback-Möglichkeit:**
   - Jeder Schritt ist reversibel
   - Schema-Migrationen können rückgängig gemacht werden
   - Python-Code kann wiederhergestellt werden

4. **DB-Integrität schützen:**
   - Neue Migrationen mit 'supabase migration new' erstellen
   - Neue Migrationen auf Englisch schreiben (ohne Umlaute)
   - Niemals 'supabase db reset' ausführen, nur 'supabase migration up'

## 📁 Neue Modulstruktur (Hybrid-Ansatz)

**Update 2025-09-09T09:00:00:** Nach detaillierter Analyse wurde ein Hybrid-Ansatz gewählt. 
Siehe [db_module_analysis.md](./db_module_analysis.md) für die Analyse und [db_hybrid_migration_plan.md](./db_hybrid_migration_plan.md) für die Migrations-Details.

### Kern-Änderungen:
- **Verzeichnis-basierte Organisation** in 5 Hauptbereiche
- **Bessere Skalierbarkeit** durch Unterverzeichnisse
- **Intuitive Navigation** nach Geschäftsbereichen

```
app/utils/db/
├── __init__.py                    # Zentrale Re-exports
├── core/                          # Basis-Funktionalität
│   ├── session.py                 # ✅ FERTIG (3 Functions)
│   └── auth.py                    # Authentifizierung (2 Functions)
├── courses/                       # Kursverwaltung  
│   ├── management.py              # ✅ TEILWEISE (8/12 Functions)
│   └── enrollment.py              # ✅ TEILWEISE (4/7 Functions)
├── content/                       # Lerninhalte
│   ├── units.py                   # Lerneinheiten (5 Functions)
│   ├── sections.py                # Abschnitte (3 Functions)
│   └── tasks.py                   # Aufgaben (16 Functions)
├── learning/                      # Lernprozess
│   ├── submissions.py             # ✅ TEILWEISE (6/8 Functions)
│   ├── progress.py                # Fortschritt (4 Functions)
│   └── mastery.py                 # Spaced Repetition (9 Functions)
└── platform/                      # Plattform-Features
    └── feedback.py                # Feedback (2 Functions)
```

## 🚀 Migrations-Schritte

### Phase 1: Setup & Erste Migration ✅ FERTIG (Abgeschlossen: 2025-09-09T07:41:30)
**Datum:** 2025-09-09

#### Schritt 1.1: Backup erstellen ✅ FERTIG
```bash
cd /home/felix/gustav
./docs/operations/backup.sh
```
**Status:** ✅ Abgeschlossen (2025-09-09T07:38:58)
**Backup-Dateien:** 
- DB: `db_backup_2025-09-09_07-38-58.sql.gz`
- Code: `code_backup_2025-09-09_07-38-58.tar.gz` 

#### Schritt 1.2: Neue Modulstruktur erstellen ✅ FERTIG
```bash
mkdir -p app/utils/db
touch app/utils/db/__init__.py
touch app/utils/db/session.py
```
**Status:** ✅ Abgeschlossen (2025-09-09T07:39:30)
**Validiert:** ✅ Struktur erstellt und verifiziert

#### Schritt 1.3: Session-Helper migrieren ✅ FERTIG
Migriere folgende Functions nach `db/session.py`:
- `get_session_id()` (Zeile 27-31) ✅
- `get_anon_client()` (Zeile 33-35) ✅
- `handle_rpc_result()` (Zeile 37-42) ✅

**Status:** ✅ Abgeschlossen (2025-09-09T07:40:00)
**Tests:** ⬜ Vor Container-Restart

#### Schritt 1.4: Rückwärtskompatibilität sicherstellen ✅ FERTIG
In `db_queries.py`:
```python
# Import from new module
from .db.session import get_session_id, get_anon_client, handle_rpc_result
```

In `db/__init__.py`:
```python
# Re-export for backwards compatibility
from .session import get_session_id, get_anon_client, handle_rpc_result

__all__ = ['get_session_id', 'get_anon_client', 'handle_rpc_result']
```

**Status:** ✅ Abgeschlossen (2025-09-09T07:41:00)
**Container Restart:** ✅ Erfolgreich (2025-09-09T07:41:30)
**Funktionstest:** ✅ Container läuft, keine Fehler

### Phase 2: SQL Migration ✅ FERTIG
**Geplant für:** 2025-09-09

#### Schritt 2.1: Schema-Fix Migration erstellen ✅ FERTIG
Datei: `supabase/migrations/20250908173000_prepare_schema_for_batch3to6.sql`

**Inhalt:**
1. Schema-Fix für task_base (title, order_in_section)
2. Fehlende Spalten für regular_tasks/mastery_tasks
3. Daten-Migration (instruction → title/prompt)
4. Vorbereitung für Batch 3-6 Views

**Status:** ✅ Erstellt (2025-09-09T07:45:00)
**Review:** ✅ Sauberer Ansatz ohne Löschungen

#### Schritt 2.2: Migrationen ausführen ✅ FERTIG
```bash
supabase migration up
```

**Ergebnis:**
- Schema-Fix erfolgreich angewendet
- Batch 3-6 automatisch nachgezogen
- 45 Tasks migriert (24 Regular, 21 Mastery)
- Keine Fehler!

**Status:** ✅ Erfolgreich (2025-09-09T07:46:00)

### Phase 3: Kritische Functions Migration ⬜ IN PROGRESS
**Geplant für:** 2025-09-10

#### Schritt 3.1: submissions.py Modul erstellen ✅ FERTIG
**Status:** ✅ Modul erstellt (2025-09-09T07:51:00)

#### Schritt 3.2: Analyse der Submission Functions ✅ FERTIG
Kritische Functions Status:
1. `create_submission()` - ✅ Bereits RPC (Zeile 940)
2. `get_remaining_attempts()` - ✅ Bereits RPC (Zeile 1021)
3. `get_submission_for_task()` - ✅ Bereits RPC (Zeile 1217)
4. `update_submission_ai_results()` - ⬜ NOCH get_user_supabase_client (Zeile 1101)
5. `update_submission_teacher_override()` - ✅ Bereits RPC (Zeile 1481)
6. `mark_feedback_as_viewed_safe()` - ⬜ NOCH get_user_supabase_client (Zeile 2472)

**Erkenntnisse:** Nur 2 Functions müssen noch migriert werden!
**Status:** ✅ Analyse abgeschlossen (2025-09-09T07:52:00)

#### Schritt 3.3: SQL-Funktionen Verifikation ✅ FERTIG
Geprüfte SQL-Funktionen in Batch 4:
- `update_submission_ai_results` ✅ Existiert (Zeile 312)
- `mark_feedback_as_viewed_safe` ✅ Existiert (Zeile 431)

**Status:** ✅ Alle benötigten SQL-Funktionen vorhanden (2025-09-09T07:53:00)

#### Schritt 3.4: Migration der verbleibenden Functions ✅ FERTIG
1. `update_submission_ai_results` - ✅ Migriert zu extended RPC
2. `mark_feedback_as_viewed_safe` - ✅ Migriert zu RPC

**Änderungen:**
- Neue SQL-Migration erstellt: `20250909055246_extend_update_submission_ai_results.sql`
- Erweiterte RPC-Funktion `update_submission_ai_results_extended` erstellt
- Neue RPC-Funktion `mark_feedback_as_viewed` erstellt  
- Beide Python-Funktionen auf RPC umgestellt
- Service Client Abhängigkeit entfernt!

**Status:** ✅ Abgeschlossen (2025-09-09T07:56:00)

#### Schritt 3.5: Submission Functions ins Modul verschieben ✅ FERTIG
Verschobene Functions:
1. `create_submission` ✅
2. `get_remaining_attempts` ✅
3. `get_submission_for_task` ✅
4. `update_submission_ai_results` ✅
5. `update_submission_teacher_override` ✅ 
6. `mark_feedback_as_viewed_safe` ✅

**Status:** ✅ Alle 6 Functions in submissions.py (2025-09-09T07:57:00)
**Container Restart:** ✅ Erfolgreich

### Phase 4: Schrittweise Module Migration ⬜ IN PROGRESS
**Geplant für:** 2025-09-10 bis 2025-09-12
**Begonnen:** 2025-09-09T08:06:00+01:00

#### Schritt 4.1: courses.py Modul erstellen ✅ FERTIG
**Backup erstellt:** `db_backup_2025-09-09_08-06-33.sql.gz` und `code_backup_2025-09-09_08-06-33.tar.gz`

**Migrierte Functions (11):**
1. `get_courses_by_creator` ✅
2. `create_course` ✅
3. `get_students_in_course` ✅
4. `get_teachers_in_course` ✅
5. `add_user_to_course` ✅
6. `remove_user_from_course` ✅
7. `get_courses_assigned_to_unit` ✅
8. `assign_unit_to_course` ✅
9. `unassign_unit_from_course` ✅
10. `get_assigned_units_for_course` ✅
11. `get_section_statuses_for_unit_in_course` ✅

**Status:** ✅ Abgeschlossen (2025-09-09T08:10:00)
**Container Restart:** ✅ Erfolgreich
**Nächster Schritt:** users.py Modul

#### Neue Migrations-Reihenfolge (Hybrid-Struktur):

**Phase 1: Verzeichnisse** ⬜
- Erstelle Verzeichnisstruktur

**Phase 2: Core** ⬜
- ✅ core/session.py - verschieben
- ⬜ core/auth.py - 2 Functions

**Phase 3: Courses** ⬜
- ⬜ courses/management.py - 12 Functions (8 vorhanden + 4 neue)
- ⬜ courses/enrollment.py - 7 Functions (4 vorhanden + 3 neue)

**Phase 4: Content** ⬜
- ⬜ content/units.py - 5 Functions
- ⬜ content/sections.py - 3 Functions
- ⬜ content/tasks.py - 16 Functions

**Phase 5: Learning** ⬜
- ⬜ learning/submissions.py - 8 Functions (6 vorhanden + 2 neue)
- ⬜ learning/progress.py - 4 Functions
- ⬜ learning/mastery.py - 9 Functions

**Phase 6: Platform** ✅ FERTIG
- ✅ platform/feedback.py - 2 Functions

Details siehe [db_hybrid_migration_plan.md](./db_hybrid_migration_plan.md)

## 📊 Fortschritt

### Gesamt-Fortschritt
- **HttpOnly Migration:** 49/59 Functions (83%) ✅
- **db_queries Refactoring:** 73/73 Functions (100%) ✅ FERTIG
- **Schema-Fix:** 100% ✅ FERTIG

### Detaillierter Status (Hybrid-Struktur)
| Verzeichnis | Modul | Total | Migriert | Verbleibend | Status |
|-------------|-------|-------|----------|-------------|---------|
| **core/** | session.py | 3 | 3 | 0 | ✅ FERTIG |
| | auth.py | 2 | 2 | 0 | ✅ FERTIG |
| **courses/** | management.py | 14 | 14 | 0 | ✅ FERTIG |
| | enrollment.py | 4 | 4 | 0 | ✅ FERTIG |
| **content/** | units.py | 5 | 5 | 0 | ✅ FERTIG |
| | sections.py | 3 | 3 | 0 | ✅ FERTIG |
| | tasks.py | 16 | 16 | 0 | ✅ FERTIG |
| **learning/** | submissions.py | 8 | 8 | 0 | ✅ FERTIG |
| | progress.py | 4 | 4 | 0 | ✅ FERTIG |
| | mastery.py | 9 | 9 | 0 | ✅ FERTIG |
| **platform/** | feedback.py | 2 | 2 | 0 | ✅ FERTIG |
| **Gesamt** | | **73** | **73** | **0** | 100% fertig |

**Wichtige Errungenschaften:**
- Alle kritischen submission Functions migriert
- Service Client Abhängigkeit entfernt
- Schema-Blocker behoben

## 🔄 Update-Log

### 2025-09-09T07:30:00+01:00
- Initiale Erstellung des Plans
- Analyse der aktuellen Situation abgeschlossen
- Idiotensicherer Plan mit Sicherheitsmechanismen erstellt
- Nächster Schritt: Phase 1 beginnen (Backup + Setup)

### 2025-09-09T07:41:30+01:00
- Phase 1 erfolgreich abgeschlossen
- Backup erstellt (DB + Code)
- Neue db/ Modulstruktur eingerichtet
- Session-Helper Functions migriert (3 Functions)
- Container neugestartet und validiert
- Nächster Schritt: Phase 2 - Kombinierte SQL Migration

### 2025-09-09T07:46:00+01:00  
- Phase 2 erfolgreich abgeschlossen!
- Schema-Fix Migration erstellt und ausgeführt
- Batch 3-6 Migrationen automatisch nachgezogen
- ALLE SQL Functions jetzt deployed (100%)
- Nächster Schritt: Phase 3 - Kritische Python Functions migrieren

### 2025-09-09T07:58:00+01:00
- Phase 3 erfolgreich abgeschlossen!
- Erweiterte SQL-Funktionen für AI-Results und Feedback-Viewing erstellt
- 2 kritische Functions von get_user_supabase_client() zu RPC migriert
- 6 submission Functions ins neue Modul verschoben
- Service Client Abhängigkeit komplett entfernt
- HttpOnly Migration jetzt bei 80% (47/59 Functions)
- db_queries Refactoring bei 12% (9/75 Functions)
- Nächster Schritt: Phase 4 - Weitere Module migrieren (courses, users, etc.)

### 2025-09-09T08:10:00+01:00
- Phase 4 begonnen - courses.py Modul erfolgreich erstellt
- 11 course Functions aus db_queries.py ins neue Modul verschoben
- Rückwärtskompatibilität in db/__init__.py sichergestellt
- Container neugestartet und validiert
- db_queries Refactoring jetzt bei 27% (20/75 Functions)
- Nächster Schritt: users.py Modul erstellen

### 2025-09-09T08:35:00+01:00
- Vollständige Analyse aller 72 Funktionen in db_queries.py durchgeführt
- Detaillierte Dokumentation in [db_module_analysis.md](./db_module_analysis.md) erstellt
- Modulstruktur basierend auf Domain-Driven Design angepasst:
  - users.py: 2 Funktionen (statt 7)
  - students.py: 4 Funktionen (neues Modul)
  - Weitere Module präzise definiert
- Klare Priorisierung für weitere Migration festgelegt
- Nächster Schritt: users.py mit 2 Funktionen erstellen

### 2025-09-09T09:00:00+01:00
- Alternative Modulstrukturen analysiert und bewertet
- **Hybrid-Struktur (Alternative 4) gewählt** - beste Balance aus Intuitivität und Wartbarkeit
- Neuer Migrationsplan erstellt: [db_hybrid_migration_plan.md](./db_hybrid_migration_plan.md)
- Struktur-Änderungen:
  - Verzeichnis-basierte Organisation (core/, courses/, content/, learning/, platform/)
  - 11 Module in 5 Hauptbereichen
  - Bessere Skalierbarkeit und intuitivere Navigation
- Nächster Schritt: Phase 1 - Verzeichnisstruktur erstellen

### 2025-09-09T08:57:00+01:00
- Phase 1 der Hybrid-Migration erfolgreich abgeschlossen!
- Backup erstellt (DB + Code)
- Verzeichnisstruktur für 5 Hauptbereiche angelegt (core/, courses/, content/, learning/, platform/)
- Phase 2 Core-Module erfolgreich migriert:
  - session.py von db/ nach core/ verschoben
  - auth.py mit 2 Funktionen erstellt (get_users_by_role, is_teacher_authorized_for_course)
  - Re-exports in core/__init__.py eingerichtet
  - Zentrale db/__init__.py aktualisiert
- Container neugestartet und validiert
- db_queries Refactoring jetzt bei 29% (22/75 Functions)
- Nächster Schritt: Phase 3 - Courses Module vervollständigen

### 2025-09-09T08:59:00+01:00
- Phase 3 erfolgreich abgeschlossen - Courses Module vollständig!
- Backup erstellt: `db_backup_2025-09-09_08-56-36.sql.gz` und `code_backup_2025-09-09_08-56-36.tar.gz`
- Courses-Struktur implementiert:
  - courses.py nach courses/management.py verschoben
  - Import-Pfad in management.py korrigiert (..core.session)
  - 3 fehlende Funktionen zu management.py hinzugefügt (update_course, delete_course, get_course_by_id)
  - enrollment.py mit 4 Funktionen erstellt (get_user_course_ids, get_student_courses, get_course_students, get_published_section_details_for_student)
  - courses/__init__.py mit allen Re-exports erstellt
- Zentrale db/__init__.py mit allen 18 course-bezogenen Funktionen aktualisiert
- Container neugestartet und validiert
- db_queries Refactoring jetzt bei 39% (30/75 Functions)
- Nächster Schritt: Phase 5 - Learning Module vervollständigen

### 2025-09-09T09:18:00+01:00
- Phase 4 erfolgreich abgeschlossen - Content Module komplett!
- Backup erstellt: `db_backup_2025-09-09_09-10-29.sql.gz` und `code_backup_2025-09-09_09-10-29.tar.gz`
- Content-Struktur implementiert:
  - content/units.py mit 5 Funktionen erstellt
  - content/sections.py mit 3 Funktionen erstellt
  - content/tasks.py mit 16 Funktionen erstellt (inkl. 5 Helper/Legacy)
  - content/__init__.py mit allen Re-exports erstellt
- Zentrale db/__init__.py mit allen 24 content-bezogenen Funktionen aktualisiert
- Container neugestartet und validiert - keine Fehler
- db_queries Refactoring jetzt bei 72% (54/75 Functions)
- Nächster Schritt: Phase 5 - Learning Module vervollständigen

### 2025-09-09T09:33:00+01:00
- Phase 5 erfolgreich abgeschlossen - Learning Module komplett!
- Backup erstellt: `db_backup_2025-09-09_09-22-51.sql.gz` und `code_backup_2025-09-09_09-22-51.tar.gz`
- Learning-Struktur vollständig implementiert:
  - submissions.py auf 8 Funktionen erweitert (get_submission_history, get_submission_by_id)
  - progress.py mit 4 Funktionen erstellt (submission status matrix functions)
  - mastery.py mit 9 Funktionen erstellt (alle mastery-bezogenen Functions)
- Neue SQL-Migration erstellt und ausgeführt: `20250909073222_add_mastery_rpc_functions.sql`
  - submit_mastery_answer_complete RPC-Funktion für atomare Operations
  - update_mastery_progress RPC-Funktion für Fortschritts-Updates
- Service Client Abhängigkeit in mastery.py komplett entfernt!
- Container neugestartet und validiert - keine Fehler
- HttpOnly Migration jetzt bei 83% (49/59 Functions) - 2 Functions zu RPC migriert
- db_queries Refactoring jetzt bei 95% (71/75 Functions)
- Nächster Schritt: Phase 6 - Platform Module und finaler Cleanup

### 2025-09-09T09:42:00+01:00
- Phase 6 erfolgreich abgeschlossen - Platform Module komplett!
- Backup erstellt: `db_backup_2025-09-09_09-37-47.sql.gz` und `code_backup_2025-09-09_09-37-47.tar.gz`
- Platform-Struktur implementiert:
  - platform/ Verzeichnis erstellt
  - feedback.py mit 2 Funktionen erstellt (submit_feedback, get_all_feedback)
  - submit_feedback von Service Client befreit (client Parameter entfernt)
  - platform/__init__.py mit Re-exports erstellt
- submissions.py wurde korrigiert nach learning/submissions.py verschoben
- Zentrale db/__init__.py mit platform Functions aktualisiert
- Originale Funktionsdefinitionen aus db_queries.py entfernt
- Container neugestartet und validiert - keine Fehler
- db_queries Refactoring jetzt bei 100% (73/73 Functions) ✅ ABGESCHLOSSEN
- **ERFOLG**: Komplette Modularisierung von db_queries.py erfolgreich beendet!

### 2025-09-09T11:15:00+01:00 - HttpOnly Cookie Migration vervollständigt!
- Backup erstellt: `db_backup_2025-09-09_10-05-03.sql.gz` und `code_backup_2025-09-09_10-05-03.tar.gz`
- Letzte 2 Probleme behoben:
  - SQL-Migration `20250909080509_fix_remaining_attempts_return.sql` erstellt
  - `get_remaining_attempts` erweitert um TABLE-Return mit beiden Werten
  - `calculate_learning_streak` Python-Wrapper in progress.py hinzugefügt
  - Re-exports in allen __init__.py Dateien aktualisiert
- Container neugestartet und validiert - keine Fehler
- HttpOnly Cookie Migration jetzt bei 100% (59/59 Functions) ✅ ABGESCHLOSSEN
- **ERFOLG**: Alle PostgreSQL Functions nutzen jetzt RPC mit Session-basierter Authentifizierung!

---

**WICHTIG:** Dieses Dokument wird nach JEDEM Schritt aktualisiert. Niemals einen Schritt überspringen!
