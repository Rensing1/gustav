# Hybrid DB Module Migration Plan

**Erstellt:** 2025-09-09T09:00:00+01:00  
**Status:** Genehmigt  
**Ziel:** Migration zu Hybrid-Struktur (Alternative 4)

## Übersicht

Nach detaillierter Analyse aller 72 Funktionen in `db_queries.py` wurde ein Hybrid-Ansatz gewählt, der die Vorteile verschiedener Architekturen kombiniert.

## Designprinzipien

1. **Klare Domänentrennung**: Jedes Verzeichnis repräsentiert einen Geschäftsbereich
2. **Kohäsion**: Zusammengehörige Funktionen im selben Modul
3. **Single Responsibility**: Jedes Modul hat einen klaren Zweck
4. **Intuitive Navigation**: Entwickler finden Funktionen dort, wo sie sie erwarten

## 📁 Finale Struktur mit Funktionszuordnung

```
app/utils/db/
├── __init__.py                    # Zentrale Re-exports für Rückwärtskompatibilität
│
├── core/                          # Basis-Funktionalität (5 Functions)
│   ├── __init__.py               
│   ├── session.py                 # ✅ FERTIG (3 Functions)
│   │   ├── get_session_id
│   │   ├── get_anon_client
│   │   └── handle_rpc_result
│   └── auth.py                    # NEU (2 Functions)
│       ├── get_users_by_role
│       └── is_teacher_authorized_for_course
│
├── courses/                       # Kursverwaltung (19 Functions)
│   ├── __init__.py
│   ├── management.py              # TEILWEISE (12 Functions)
│   │   ├── get_courses_by_creator ✅
│   │   ├── create_course ✅
│   │   ├── update_course
│   │   ├── delete_course
│   │   ├── get_course_by_id
│   │   ├── get_courses_assigned_to_unit ✅
│   │   ├── assign_unit_to_course ✅
│   │   ├── unassign_unit_from_course ✅
│   │   ├── get_assigned_units_for_course ✅
│   │   ├── get_section_statuses_for_unit_in_course ✅
│   │   ├── publish_section_for_course
│   │   └── unpublish_section_for_course
│   └── enrollment.py              # TEILWEISE (7 Functions)
│       ├── get_students_in_course ✅
│       ├── get_teachers_in_course ✅
│       ├── add_user_to_course ✅
│       ├── remove_user_from_course ✅
│       ├── get_user_course_ids
│       ├── get_student_courses
│       └── get_course_students
│
├── content/                       # Lerninhalte (24 Functions)
│   ├── __init__.py
│   ├── units.py                   # NEU (5 Functions)
│   │   ├── get_learning_units_by_creator
│   │   ├── create_learning_unit
│   │   ├── update_learning_unit
│   │   ├── delete_learning_unit
│   │   └── get_learning_unit_by_id
│   ├── sections.py                # NEU (3 Functions)
│   │   ├── get_sections_for_unit
│   │   ├── create_section
│   │   └── update_section_materials
│   └── tasks.py                   # NEU (16 Functions)
│       ├── create_regular_task
│       ├── create_mastery_task
│       ├── update_task_in_new_structure
│       ├── delete_task_in_new_structure
│       ├── get_tasks_for_section
│       ├── get_regular_tasks_for_section
│       ├── get_mastery_tasks_for_section
│       ├── get_section_tasks
│       ├── get_task_details
│       ├── move_task_up
│       ├── move_task_down
│       └── [+ 5 Helper/Legacy Functions]
│
├── learning/                      # Lernprozess (21 Functions)
│   ├── __init__.py
│   ├── submissions.py             # TEILWEISE (8 Functions)
│   │   ├── create_submission ✅
│   │   ├── get_submission_history
│   │   ├── get_remaining_attempts ✅
│   │   ├── get_submission_by_id
│   │   ├── get_submission_for_task ✅
│   │   ├── update_submission_ai_results ✅
│   │   ├── update_submission_teacher_override ✅
│   │   └── mark_feedback_as_viewed_safe ✅
│   ├── progress.py                # NEU (4 Functions)
│   │   ├── get_submission_status_matrix
│   │   ├── get_submissions_for_course_and_unit
│   │   ├── calculate_learning_streak
│   │   └── get_published_section_details_for_student
│   └── mastery.py                 # NEU (9 Functions)
│       ├── get_mastery_tasks_for_course
│       ├── get_next_due_mastery_task
│       ├── get_next_mastery_task_or_unviewed_feedback
│       ├── save_mastery_submission
│       ├── submit_mastery_answer
│       ├── get_mastery_stats_for_student
│       ├── get_mastery_overview_for_teacher
│       ├── get_mastery_progress_summary
│       └── _update_mastery_progress
│
└── platform/                      # Plattform-Features (2 Functions)
    ├── __init__.py
    └── feedback.py                # NEU (2 Functions)
        ├── submit_feedback
        └── get_all_feedback
```

## 📊 Statistiken der neuen Struktur

| Verzeichnis | Module | Functions | Durchschnitt |
|-------------|--------|-----------|--------------|
| core | 2 | 5 | 2.5 |
| courses | 2 | 19 | 9.5 |
| content | 3 | 24 | 8.0 |
| learning | 3 | 21 | 7.0 |
| platform | 1 | 2 | 2.0 |
| **Gesamt** | **11** | **71** | **6.5** |

## 🚀 Migrations-Roadmap

### Phase 1: Verzeichnisstruktur (Sofort)
```bash
mkdir -p app/utils/db/{core,courses,content,learning,platform}
touch app/utils/db/{core,courses,content,learning,platform}/__init__.py
```
- [ ] Verzeichnisse erstellen
- [ ] __init__.py Dateien anlegen
- [ ] Backup erstellen

### Phase 2: Core Module (Tag 1)
- [x] `core/session.py` - bereits fertig, nur verschieben
- [ ] `core/auth.py` - 2 Functions (get_users_by_role, is_teacher_authorized_for_course)
- [ ] Re-exports in core/__init__.py

### Phase 3: Courses vervollständigen (Tag 2-3)
- [ ] `courses/management.py` - 3 neue Functions (update_course, delete_course, get_course_by_id)
- [ ] `courses/enrollment.py` - 3 Functions verschieben
- [ ] Publishing-Functions zu management.py
- [ ] Re-exports aktualisieren

### Phase 4: Content Module (Tag 4-6)
- [ ] `content/units.py` - 5 Functions
- [ ] `content/sections.py` - 3 Functions
- [ ] `content/tasks.py` - 16 Functions (inkl. Helper)
- [ ] Legacy-Functions dokumentieren

### Phase 5: Learning Module (Tag 7-9)
- [ ] `learning/submissions.py` - 2 Functions ergänzen
- [ ] `learning/progress.py` - 4 Functions
- [ ] `learning/mastery.py` - 9 Functions (komplexeste Migration)
- [ ] RPC-Migration für Legacy-Functions

### Phase 6: Platform & Cleanup (Tag 10)
- [ ] `platform/feedback.py` - 2 Functions
- [ ] Finale Re-export Struktur
- [ ] db_queries.py aufräumen
- [ ] Integration tests

## 🔄 Migration von bestehenden Modulen

### Bereits existierende Module
1. **session.py** → `core/session.py` (nur verschieben)
2. **courses.py** → `courses/management.py` (aufteilen)
3. **submissions.py** → `learning/submissions.py` (ergänzen)

### Import-Mapping für Rückwärtskompatibilität
```python
# app/utils/db/__init__.py
# Alte imports weiterhin unterstützen
from .core.session import get_session_id, get_anon_client, handle_rpc_result
from .core.auth import get_users_by_role, is_teacher_authorized_for_course
from .courses.management import get_courses_by_creator, create_course, ...
# etc.
```

## ✅ Vorteile der Hybrid-Struktur

1. **Intuitive Navigation**: Klare Geschäftsbereiche
2. **Skalierbarkeit**: Neue Features finden leicht ihren Platz
3. **Wartbarkeit**: Kleine, fokussierte Module
4. **Developer Experience**: Selbsterklärende Imports
5. **Graduelle Migration**: Schrittweise umsetzbar

## 🚨 Wichtige Hinweise

- **Keine Breaking Changes**: Alle bestehenden Imports bleiben funktionsfähig
- **Backup vor jeder Phase**: Sicherheit geht vor
- **Container-Neustart**: Nach jeder Phase validieren
- **Dokumentation**: Jede Phase im Plan dokumentieren

## Status-Tracker

- [ ] Dokumentation genehmigt
- [ ] Phase 1: Verzeichnisstruktur
- [ ] Phase 2: Core Module
- [ ] Phase 3: Courses Module
- [ ] Phase 4: Content Module
- [ ] Phase 5: Learning Module
- [ ] Phase 6: Platform & Cleanup
- [ ] Migration abgeschlossen
- [ ] Legacy cleanup
- [ ] Finale Tests