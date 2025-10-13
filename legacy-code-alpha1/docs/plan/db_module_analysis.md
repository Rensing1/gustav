# Detaillierte DB-Modul Analyse

**Erstellt:** 2025-09-09T08:30:00+01:00  
**Status:** Vollständige Analyse aller Funktionen in db_queries.py  
**Zweck:** Fundierte Grundlage für die Modularisierung

## Zusammenfassung

Diese Analyse untersucht alle 72 Funktionen in `db_queries.py` und schlägt eine sinnvolle Aufteilung in Module vor. Von den 72 Funktionen sind bereits 11 migriert, 61 müssen noch verschoben werden.

## Detaillierte Funktionsanalyse und Kategorisierung

### 1. **Benutzerverwaltung & Authentifizierung**

#### **users.py** - Allgemeine Benutzerverwaltung (2 Funktionen)
```
get_users_by_role (342)
- Zweck: Lädt alle Benutzer mit einer bestimmten Rolle (student/teacher)
- Verwendung: Admin-Interface, Benutzerauswahl in Formularen
- RPC: ✅

is_teacher_authorized_for_course (2194) 
- Zweck: Prüft ob Session-User berechtigt ist, einen Kurs zu verwalten
- Verwendung: Zugangskontrolle für Kursbearbeitung
- RPC: ✅
```

### 2. **Kursverwaltung**

#### **courses.py** - Kurs-CRUD und Beziehungen (14 Funktionen)
```
BEREITS MIGRIERT:
get_courses_by_creator (282) - Lädt Kurse des aktuellen Users
create_course (301) - Erstellt neuen Kurs
get_students_in_course (370) - Lädt eingeschriebene Studenten
get_teachers_in_course (407) - Lädt zugewiesene Lehrer
add_user_to_course (446) - Fügt Student/Lehrer zu Kurs hinzu
remove_user_from_course (482) - Entfernt Student/Lehrer aus Kurs
get_courses_assigned_to_unit (521) - Kurse die eine Lerneinheit nutzen
assign_unit_to_course (560) - Weist Lerneinheit zu Kurs zu
unassign_unit_from_course (592) - Entfernt Lerneinheit von Kurs
get_assigned_units_for_course (657) - Alle Lerneinheiten eines Kurses
get_section_statuses_for_unit_in_course (698) - Publikationsstatus der Sections

NOCH ZU MIGRIEREN:
update_course (2129) - Aktualisiert Kursnamen
delete_course (2162) - Löscht Kurs komplett
get_course_by_id (2234) - Lädt einzelnen Kurs
```

### 3. **Student-spezifische Funktionen**

#### **students.py** - Studentenansichten und -daten (4 Funktionen)
```
get_user_course_ids (791)
- Zweck: Lädt nur Kurs-IDs für Memory-Management
- Verwendung: Session-State, Performance-Optimierung
- RPC: ✅

get_student_courses (826)
- Zweck: Lädt Kurse mit Namen für UI
- Verwendung: Kursauswahl für Studenten
- RPC: ✅

get_published_section_details_for_student (868)
- Zweck: Lädt veröffentlichte Inhalte mit Submission-Status
- Verwendung: Hauptansicht für Studenten
- RPC: ✅

get_course_students (1240)
- Zweck: Lädt alle Studenten eines Kurses für Lehrer
- Verwendung: Teilnehmerlisten, Fortschrittsübersicht
- RPC: ✅
```

### 4. **Lerneinheiten (Learning Units)**

#### **learning_units.py** - Lerneinheiten-Verwaltung (5 Funktionen)
```
get_learning_units_by_creator (1582) - Lädt eigene Lerneinheiten
create_learning_unit (1600) - Erstellt neue Lerneinheit
update_learning_unit (1638) - Aktualisiert Titel
delete_learning_unit (1670) - Löscht Lerneinheit
get_learning_unit_by_id (1701) - Lädt einzelne Einheit
```

### 5. **Sections (Abschnitte)**

#### **sections.py** - Abschnittsverwaltung (5 Funktionen)
```
get_sections_for_unit (626)
- Zweck: Lädt alle Abschnitte einer Lerneinheit für Bearbeitung
- RPC: ✅

create_section (1735)
- Zweck: Erstellt neuen Abschnitt in Lerneinheit
- RPC: ✅

update_section_materials (1778)
- Zweck: Aktualisiert Lernmaterialien eines Abschnitts
- RPC: ✅

publish_section_for_course (737)
- Zweck: Macht Abschnitt für Kurs sichtbar
- RPC: ✅

unpublish_section_for_course (764)
- Zweck: Versteckt Abschnitt vor Studenten
- RPC: ✅
```

### 6. **Aufgaben (Tasks)**

#### **tasks.py** - Aufgabenverwaltung (11 Funktionen + 6 Legacy)
```
CRUD-Operationen:
create_regular_task (50) - Erstellt normale Aufgabe
create_mastery_task (99) - Erstellt Mastery-Aufgabe
update_task_in_new_structure (191) - Aktualisiert Aufgabe
delete_task_in_new_structure (231) - Löscht Aufgabe

Abfragen:
get_tasks_for_section (1811) - Alle Aufgaben eines Abschnitts
get_regular_tasks_for_section (1860) - Nur normale Aufgaben
get_mastery_tasks_for_section (1899) - Nur Mastery-Aufgaben
get_section_tasks (1287) - Alternative Abfrage
get_task_details (1065) - Detailinfos einer Aufgabe

Reihenfolge:
move_task_up (2067) - Verschiebt Aufgabe nach oben
move_task_down (2098) - Verschiebt Aufgabe nach unten

Legacy (DEPRECATED):
create_task (1939) - Alte Implementierung
update_task (1994) - Alte Implementierung
delete_task (2043) - Alte Implementierung
create_task_in_new_structure (146) - Übergangs-Wrapper
_get_task_table_name (39) - Helper
get_regular_tasks_table_name (261) - Helper
get_mastery_tasks_table_name (267) - Helper
```

### 7. **Einreichungen (Submissions)**

#### **submissions.py** - Studenteneinreichungen (8 Funktionen)
```
BEREITS MIGRIERT:
create_submission (940) - Neue Einreichung erstellen
get_remaining_attempts (1021) - Verbleibende Versuche
get_submission_for_task (1204) - Letzte Einreichung für Aufgabe
update_submission_ai_results (1101) - KI-Bewertung speichern
update_submission_teacher_override (1468) - Lehrerbewertung
mark_feedback_as_viewed_safe (2459) - Feedback als gelesen markieren

NOCH ZU MIGRIEREN:
get_submission_history (998) - Alle Einreichungen eines Students
get_submission_by_id (1168) - Einzelne Einreichung laden
```

### 8. **Fortschritt & Analytik**

#### **progress.py** - Fortschrittsverfolgung (3 Funktionen)
```
get_submission_status_matrix (1335)
- Zweck: Matrix aller Submissions für Kurs (Teacher-View)
- Mit Caching für Performance
- RPC: ✅

get_submissions_for_course_and_unit (1523)
- Zweck: Detaillierte Submissions für eine Einheit
- RPC: ✅

calculate_learning_streak (3052)
- Zweck: Berechnet Lern-Streak (aufeinanderfolgende Tage)
- User Client (noch nicht RPC)
```

### 9. **Mastery Learning System**

#### **mastery.py** - Wissensfestiger (9 Funktionen)
```
Aufgabenverwaltung:
get_mastery_tasks_for_course (2280) - Alle Mastery-Aufgaben eines Kurses
get_next_due_mastery_task (2334) - Nächste fällige Aufgabe (Spaced Repetition)
get_next_mastery_task_or_unviewed_feedback (2406) - Mit Feedback-Check

Einreichungen:
save_mastery_submission (2507) - Speichert Mastery-Antwort
submit_mastery_answer (2538) - Vollständiger Submit mit KI-Bewertung

Statistiken:
get_mastery_stats_for_student (2627) - Individuelle Statistiken
get_mastery_overview_for_teacher (2927) - Klassenübersicht
get_mastery_progress_summary (3005) - Optimierte Zusammenfassung
_update_mastery_progress (2705) - Interner Progress-Update
```

### 10. **Feedback-System**

#### **feedback.py** - Benutzerfeedback (2 Funktionen)
```
submit_feedback (2772)
- Zweck: Anonymes Feedback von Benutzern speichern
- RPC: ✅

get_all_feedback (2822)
- Zweck: Alle Feedbacks für Admins/Lehrer
- RPC: ✅
```

### 11. **Helper-Funktionen**

#### **_internal.py** oder in jeweiligen Modulen
```
_get_task_table_name (39) - Task-Tabellen-Routing
get_regular_tasks_table_name (261) - View-Name für reguläre Tasks  
get_mastery_tasks_table_name (267) - View-Name für Mastery-Tasks
_get_submission_status_matrix_cached (1331) - Cache-Helper
_get_submission_status_matrix_uncached (1357) - Direkte Abfrage
```

## Empfohlene Modulstruktur

```
app/utils/db/
├── __init__.py          # Re-exports für Rückwärtskompatibilität
├── session.py           # ✅ FERTIG (3 Functions)
├── courses.py           # ✅ TEILWEISE (11/14 Functions) 
├── users.py             # NEU: 2 Functions
├── students.py          # NEU: 4 Functions  
├── learning_units.py    # NEU: 5 Functions
├── sections.py          # NEU: 5 Functions
├── tasks.py             # NEU: 11 Functions (ohne Legacy)
├── submissions.py       # ✅ TEILWEISE (6/8 Functions)
├── progress.py          # NEU: 3 Functions
├── mastery.py           # NEU: 9 Functions
├── feedback.py          # NEU: 2 Functions
└── _legacy.py           # Deprecated Functions
```

## Statistiken

### **Funktionen nach Status:**
- **Bereits migriert:** 11 Funktionen
- **Noch in db_queries.py:** 61 Funktionen
- **Gesamt:** 72 Funktionen

### **Funktionen nach Zielmodul:**
- **tasks.py:** 17 Funktionen (11 aktiv + 6 legacy)
- **courses.py:** 14 Funktionen (11 migriert + 3 ausstehend)
- **mastery.py:** 9 Funktionen
- **submissions.py:** 8 Funktionen (6 migriert + 2 ausstehend)
- **learning_units.py:** 5 Funktionen
- **sections.py:** 5 Funktionen
- **students.py:** 4 Funktionen
- **progress.py:** 3 Funktionen
- **users.py:** 2 Funktionen
- **feedback.py:** 2 Funktionen
- **Helper/Internal:** 5 Funktionen

### **Implementierungstypen:**
- **RPC:** 45 Funktionen (meistens mit get_anon_client())
- **User Client:** 16 Funktionen (get_user_supabase_client())
- **Service Client:** 3 Funktionen (get_service_supabase_client())
- **Helper:** 8 Funktionen (interne Hilfsfunktionen)

## Migrations-Prioritäten

**Hohe Priorität (bereits RPC):**
1. users.py - 2 einfache Funktionen
2. students.py - 4 wichtige View-Funktionen
3. learning_units.py - 5 CRUD-Funktionen
4. sections.py - 5 CRUD-Funktionen
5. tasks.py - 11 zentrale Funktionen

**Mittlere Priorität (teilweise RPC):**
6. progress.py - 2 RPC + 1 zu migrieren
7. courses.py - 3 noch zu migrieren
8. feedback.py - 2 einfache Funktionen

**Niedrige Priorität (viel Legacy):**
9. mastery.py - Komplexe Logik, viel User Client
10. _legacy.py - Deprecated Functions

## Begründung der Struktur

Diese Struktur folgt dem Domain-Driven Design und gruppiert Funktionen nach ihrem Geschäftszweck:

1. **Klare Domänen:** Jedes Modul repräsentiert eine klare Geschäftsdomäne
2. **Kohäsion:** Funktionen mit ähnlichem Zweck sind zusammen
3. **Lose Kopplung:** Module sind weitgehend unabhängig
4. **Wartbarkeit:** Kleinere, fokussierte Module sind einfacher zu verstehen
5. **Schrittweise Migration:** RPC-ready Funktionen können sofort migriert werden

## Nächste Schritte

1. Aktualisierung des Migrationsplans basierend auf dieser Analyse
2. Start mit users.py (2 Funktionen) als einfachstem Modul
3. Fortsetzung mit students.py (4 Funktionen)
4. Systematische Migration der weiteren Module nach Priorität

## Finale Entscheidung: Hybrid-Struktur

**Update 2025-09-09T09:00:00:** Nach Analyse verschiedener Alternativen wurde die Hybrid-Struktur (Alternative 4) gewählt. Diese kombiniert die Vorteile von Domain-Driven Design mit praktischer Wartbarkeit.

### Gewählte Struktur
- **5 Hauptbereiche**: core, courses, content, learning, platform
- **Verzeichnis-basierte Organisation** für bessere Skalierbarkeit
- **Intuitive Zuordnung** nach Geschäftsbereichen

Details zur Migration siehe [db_hybrid_migration_plan.md](./db_hybrid_migration_plan.md)