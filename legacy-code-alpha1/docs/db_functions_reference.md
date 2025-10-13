# DB Functions Reference - Complete UI Usage Documentation

Dieses Dokument dokumentiert alle DB-Funktionsaufrufe in der GUSTAV UI mit:
- Parametern
- Erwarteter Ausgabe
- Verwendungskontext
- Bekannte Probleme

## 1. Live-Unterricht (6_Live-Unterricht.py)

### get_sections_for_unit()
**Parameter:**
- `unit_id: str` - UUID der Lerneinheit

**Erwartete Ausgabe:**
```python
(
    [
        {
            'id': str,
            'title': str,
            'order_in_unit': int,
            'materials': list
        },
        ...
    ],
    None  # oder error_message
)
```

**Verwendung:** Lädt alle Abschnitte einer Lerneinheit für die Freigabesteuerung

---

### get_section_statuses_for_unit_in_course()
**Parameter:**
- `unit_id: str` - UUID der Lerneinheit
- `course_id: str` - UUID des Kurses

**Erwartete Ausgabe:**
```python
(
    {
        section_id: bool,  # True = published, False = not published
        ...
    },
    None  # oder error_message
)
```

**Verwendung:** Prüft welche Abschnitte in einem Kurs bereits veröffentlicht sind

---

### get_submission_status_matrix()
**Parameter:**
- `course_id: str` - UUID des Kurses
- `unit_id: str` - UUID der Lerneinheit

**Erwartete Ausgabe:**
```python
(
    {
        'students': [
            {
                'student_id': str,
                'display_name': str,
                'email': str
            }
        ],
        'sections': [
            {
                'id': str,
                'title': str,
                'order': int,
                'tasks': [
                    {
                        'id': str,
                        'title': str,
                        'instruction': str,
                        'order_in_section': int
                    }
                ],
                'submissions': {
                    student_id: {
                        task_id: {
                            'status': 'submitted' | 'not_submitted',
                            'is_correct': bool,
                            'has_feedback': bool,
                            'submission_count': int,
                            'latest_submission_at': str
                        }
                    }
                }
            }
        ],
        'total_tasks': int,
        'total_submissions': int
    },
    None  # oder error_message
)
```

**Verwendung:** Lädt die komplette Matrix-Übersicht aller Schüler-Abgaben für Live-Monitoring

**⚠️ BEKANNTES PROBLEM:** Gibt aktuell 0 sections zurück, obwohl sections existieren

---

### publish_section_for_course()
**Parameter:**
- `section_id: str` - UUID des Abschnitts
- `course_id: str` - UUID des Kurses

**Erwartete Ausgabe:**
```python
(True, None)  # bei Erfolg
(False, error_message)  # bei Fehler
```

**Verwendung:** Veröffentlicht einen Abschnitt für einen bestimmten Kurs

---

### unpublish_section_for_course()
**Parameter:**
- `section_id: str` - UUID des Abschnitts
- `course_id: str` - UUID des Kurses

**Erwartete Ausgabe:**
```python
(True, None)  # bei Erfolg
(False, error_message)  # bei Fehler
```

**Verwendung:** Nimmt die Veröffentlichung eines Abschnitts zurück

---

### get_task_details()
**Parameter:**
- `task_id: str` - UUID der Aufgabe

**Erwartete Ausgabe:**
```python
(
    {
        'id': str,
        'title': str,
        'task_type': str,
        'prompt': str,
        'max_attempts': int,
        'grading_criteria': str,
        # oder für mastery tasks:
        'difficulty_level': int,
        'concept_explanation': str
    },
    None  # oder error_message
)
```

**Verwendung:** Lädt Details einer einzelnen Aufgabe für die Detailansicht

---

### get_submission_for_task()
**Parameter:**
- `student_id: str` - UUID des Schülers
- `task_id: str` - UUID der Aufgabe

**Erwartete Ausgabe:**
```python
(
    {
        'id': str,
        'submission_text': str,
        'submitted_at': str,
        'ai_feedback': str,
        'ai_grade': float,
        'is_correct': bool,
        'teacher_feedback': str,
        'override_grade': float,
        'attempt_number': int
    },
    None  # oder error_message
)
```

**Verwendung:** Lädt eine spezifische Schüler-Einreichung

---

### update_submission_teacher_override()
**Parameter:**
- `submission_id: str` - UUID der Einreichung
- `teacher_feedback: str` - Feedback-Text des Lehrers
- `teacher_grade: float` - Note (0-100)

**Erwartete Ausgabe:**
```python
(True, None)  # bei Erfolg
(False, error_message)  # bei Fehler
```

**Verwendung:** Speichert Lehrer-Feedback und Note als Override

---

## 2. Meine Aufgaben (3_Meine_Aufgaben.py)

### get_published_section_details_for_student()
**Parameter:**
- `unit_id: str` - UUID der Lerneinheit
- `course_id: str` - UUID des Kurses
- `student_id: str` - UUID des Schülers

**Erwartete Ausgabe:**
```python
(
    [
        {
            'id': str,
            'title': str,
            'order_in_unit': int,
            'materials': [
                {
                    'title': str,
                    'type': 'link' | 'file' | 'markdown' | 'applet',
                    'content': str,  # URL, Markdown-Text oder Dateipfad
                    'path': str,     # für type='file'
                    'mime_type': str # für type='file'
                }
            ],
            'tasks': [
                {
                    'id': str,
                    'title': str,
                    'task_type': str,
                    'prompt': str,
                    'max_attempts': int,
                    'order_in_section': int
                }
            ]
        }
    ],
    None  # oder error_message
)
```

**Verwendung:** Lädt veröffentlichte Abschnitte mit Materialien und Aufgaben für einen Schüler

---

### get_submission_history()
**Parameter:**
- `student_id: str` - UUID des Schülers
- `task_id: str` - UUID der Aufgabe

**Erwartete Ausgabe:**
```python
(
    [
        {
            'id': str,
            'submission_text': str,
            'submitted_at': str,
            'attempt_number': int,
            'ai_feedback': str,
            'ai_grade': float,
            'is_correct': bool
        }
    ],
    None  # oder error_message
)
```

**Verwendung:** Lädt alle bisherigen Einreichungen eines Schülers für eine Aufgabe

---

### get_remaining_attempts()
**Parameter:**
- `student_id: str` - UUID des Schülers
- `task_id: str` - UUID der Aufgabe

**Erwartete Ausgabe:**
```python
(
    {
        'remaining': int,      # Verbleibende Versuche (-1 = unbegrenzt)
        'max_attempts': int,   # Maximale Versuche
        'used_attempts': int   # Bereits genutzte Versuche
    },
    None  # oder error_message
)
```

**Verwendung:** Prüft wie viele Versuche noch übrig sind

---

### create_submission()
**Parameter:**
- `student_id: str` - UUID des Schülers
- `task_id: str` - UUID der Aufgabe
- `solution_text: str | dict` - Lösungstext oder dict mit 'answer' für mastery

**Erwartete Ausgabe:**
```python
(
    {
        'id': str,              # Submission ID
        'attempt_number': int,
        'created_at': str
    },
    None  # oder error_message
)
```

**Verwendung:** Erstellt eine neue Einreichung

---

### get_submission_by_id()
**Parameter:**
- `submission_id: str` - UUID der Einreichung

**Erwartete Ausgabe:**
```python
(
    {
        'id': str,
        'student_id': str,
        'task_id': str,
        'submission_text': str,
        'submitted_at': str,
        'ai_feedback': str,
        'ai_grade': float,
        'is_correct': bool,
        'teacher_feedback': str,
        'override_grade': float,
        'attempt_number': int,
        'is_processing': bool
    },
    None  # oder error_message
)
```

**Verwendung:** Lädt Submission-Status für Feedback-Polling

---

## 3. Kurse (1_Kurse.py)

### get_courses_by_creator()
**Parameter:**
- `teacher_id: str` - UUID des Lehrers

**Erwartete Ausgabe:**
```python
(
    [
        {
            'id': str,
            'name': str,
            'created_by': str,
            'created_at': str
        }
    ],
    None  # oder error_message
)
```

**Verwendung:** Prüft ob Lehrer bereits Kurse erstellt hat

---

### create_course()
**Parameter:**
- `name: str` - Name des Kurses
- `teacher_id: str` - UUID des Lehrers

**Erwartete Ausgabe:**
```python
(
    {
        'id': str,
        'name': str,
        'created_by': str
    },
    None  # oder error_message
)
```

**Verwendung:** Erstellt einen neuen Kurs

---

## 4. Lerneinheiten (2_Lerneinheiten.py)

### get_learning_units_by_creator()
**Parameter:**
- `teacher_id: str` - UUID des Lehrers

**Erwartete Ausgabe:**
```python
(
    [
        {
            'id': str,
            'title': str,
            'created_by': str,
            'created_at': str
        }
    ],
    None  # oder error_message
)
```

**Verwendung:** Lädt alle Lerneinheiten eines Lehrers

---

### create_learning_unit()
**Parameter:**
- `title: str` - Titel der Lerneinheit
- `teacher_id: str` - UUID des Lehrers

**Erwartete Ausgabe:**
```python
(
    {
        'id': str,
        'title': str,
        'created_by': str
    },
    None  # oder error_message
)
```

**Verwendung:** Erstellt neue Lerneinheit

---

### get_learning_unit_by_id()
**Parameter:**
- `unit_id: str` - UUID der Lerneinheit

**Erwartete Ausgabe:**
```python
(
    {
        'id': str,
        'title': str,
        'created_by': str,
        'created_at': str
    },
    None  # oder error_message
)
```

**Verwendung:** Lädt Details einer spezifischen Lerneinheit

---

### get_assigned_units_for_course()
**Parameter:**
- `course_id: str` - UUID des Kurses

**Erwartete Ausgabe:**
```python
(
    [
        {
            'id': str,
            'title': str,
            'created_by': str,
            'order_in_course': int
        }
    ],
    None  # oder error_message
)
```

**Verwendung:** Lädt Lerneinheiten eines bestimmten Kurses

---

## 5. Schüler (5_Schueler.py)

### get_students_in_course()
**Parameter:**
- `course_id: str` - UUID des Kurses

**Erwartete Ausgabe:**
```python
(
    [
        {
            'id': str,
            'email': str,
            'display_name': str,
            'role': 'student'
        }
    ],
    None  # oder error_message
)
```

**Verwendung:** Lädt Liste aller Schüler in einem Kurs

---

### get_teachers_in_course()
**Parameter:**
- `course_id: str` - UUID des Kurses

**Erwartete Ausgabe:**
```python
(
    [
        {
            'id': str,
            'email': str,
            'display_name': str,
            'role': 'teacher'
        }
    ],
    None  # oder error_message
)
```

**Verwendung:** Lädt Liste aller Lehrer in einem Kurs (inkl. Kurs-Ersteller)

---

### add_user_to_course()
**Parameter:**
- `course_id: str` - UUID des Kurses
- `user_id: str` - UUID des Benutzers
- `role: str` - 'student' oder 'teacher'

**Erwartete Ausgabe:**
```python
(True, None)  # bei Erfolg
(False, error_message)  # bei Fehler
```

**Verwendung:** Fügt Schüler oder Lehrer zu einem Kurs hinzu

---

### remove_user_from_course()
**Parameter:**
- `course_id: str` - UUID des Kurses
- `user_id: str` - UUID des Benutzers
- `role: str` - 'student' oder 'teacher'

**Erwartete Ausgabe:**
```python
(True, None)  # bei Erfolg
(False, error_message)  # bei Fehler
```

**Verwendung:** Entfernt Schüler oder Lehrer aus einem Kurs

---

## 6. Wissensfestiger (7_Wissensfestiger.py)

### get_next_mastery_task_or_unviewed_feedback()
**Parameter:**
- `student_id: str` - UUID des Schülers
- `course_id: str` - UUID des Kurses

**Erwartete Ausgabe:**
```python
(
    {
        'type': 'task' | 'feedback',
        'data': {
            # Bei type='task':
            'id': str,
            'title': str,
            'prompt': str,
            'difficulty_level': int,
            'concept_explanation': str,
            # Bei type='feedback':
            'submission_id': str,
            'ai_feedback': str,
            'is_correct': bool
        }
    },
    None  # oder error_message
)
```

**Verwendung:** Lädt nächste fällige Aufgabe oder ungelesenes Feedback

---

### mark_feedback_as_viewed_safe()
**Parameter:**
- `submission_id: str` - UUID der Submission

**Erwartete Ausgabe:**
```python
(True, None)  # bei Erfolg
(False, error_message)  # bei Fehler
```

**Verwendung:** Markiert Feedback als gelesen

---

### get_user_course_ids()
**Parameter:**
- `student_id: str` - UUID des Schülers

**Erwartete Ausgabe:**
```python
(
    [str, str, ...],  # Liste von course_ids
    None  # oder error_message
)
```

**Verwendung:** Memory-Management für Session State Cleanup

---

## 7. Feedback (8_Feedback.py & 9_Feedback_einsehen.py)

### submit_feedback()
**Parameter:**
- `feedback_type: str` - 'bug' | 'feature' | 'question' | 'other'
- `message: str` - Feedback-Text

**Erwartete Ausgabe:**
```python
(True, None)  # bei Erfolg
(False, error_message)  # bei Fehler
```

**Verwendung:** Speichert anonymes Feedback von Nutzern

---

## 8. Feedback Einsehen (9_Feedback_einsehen.py)

### get_all_feedback()
**Parameter:** Keine (nutzt Session für Authentifizierung)

**Erwartete Ausgabe:**
```python
(
    [
        {
            'id': str,
            'created_at': str,
            'user_email': str,
            'feedback_type': 'bug' | 'feature' | 'question' | 'other',
            'message': str
        }
    ],
    None  # oder error_message
)
```

**Verwendung:** Lädt alle Feedback-Einträge für Lehrer-Ansicht

---

## 9. Weitere wichtige Funktionen

### get_users_by_role()
**Parameter:**
- `role: str` - 'teacher' oder 'student'

**Erwartete Ausgabe:**
```python
(
    [
        {
            'id': str,
            'email': str,
            'display_name': str
        }
    ],
    None  # oder error_message
)
```

**Verwendung:** Lädt alle Benutzer mit einer bestimmten Rolle (nur für Lehrer)

---

### update_course()
**Parameter:**
- `course_id: str` - UUID des Kurses
- `name: str` - Neuer Name des Kurses

**Erwartete Ausgabe:**
```python
(True, None)  # bei Erfolg
(False, error_message)  # bei Fehler
```

**Verwendung:** Aktualisiert den Namen eines Kurses

---

### delete_course()
**Parameter:**
- `course_id: str` - UUID des Kurses

**Erwartete Ausgabe:**
```python
(True, None)  # bei Erfolg
(False, error_message)  # bei Fehler
```

**Verwendung:** Löscht einen Kurs (CASCADE - löscht alle verknüpften Daten)

---

### get_course_by_id()
**Parameter:**
- `course_id: str` - UUID des Kurses

**Erwartete Ausgabe:**
```python
(
    {
        'id': str,
        'name': str,
        'created_by': str,
        'created_at': str
    },
    None  # oder error_message
)
```

**Verwendung:** Lädt Details eines spezifischen Kurses

---

### update_learning_unit()
**Parameter:**
- `unit_id: str` - UUID der Lerneinheit
- `title: str` - Neuer Titel

**Erwartete Ausgabe:**
```python
(True, None)  # bei Erfolg
(False, error_message)  # bei Fehler
```

**Verwendung:** Aktualisiert den Titel einer Lerneinheit

---

### delete_learning_unit()
**Parameter:**
- `unit_id: str` - UUID der Lerneinheit

**Erwartete Ausgabe:**
```python
(True, None)  # bei Erfolg
(False, error_message)  # bei Fehler
```

**Verwendung:** Löscht eine Lerneinheit

---

### assign_unit_to_course()
**Parameter:**
- `unit_id: str` - UUID der Lerneinheit
- `course_id: str` - UUID des Kurses

**Erwartete Ausgabe:**
```python
(True, None)  # bei Erfolg
(False, error_message)  # bei Fehler
```

**Verwendung:** Weist eine Lerneinheit einem Kurs zu

---

### unassign_unit_from_course()
**Parameter:**
- `unit_id: str` - UUID der Lerneinheit
- `course_id: str` - UUID des Kurses

**Erwartete Ausgabe:**
```python
(True, None)  # bei Erfolg
(False, error_message)  # bei Fehler
```

**Verwendung:** Entfernt eine Lerneinheit aus einem Kurs

---

### get_courses_assigned_to_unit()
**Parameter:**
- `unit_id: str` - UUID der Lerneinheit

**Erwartete Ausgabe:**
```python
(
    [
        {
            'id': str,
            'name': str,
            'created_by': str
        }
    ],
    None  # oder error_message
)
```

**Verwendung:** Lädt alle Kurse, in denen eine Lerneinheit verwendet wird

---

### create_section()
**Parameter:**
- `unit_id: str` - UUID der Lerneinheit
- `title: str` - Titel des Abschnitts
- `order_in_unit: int` - Position in der Lerneinheit

**Erwartete Ausgabe:**
```python
(
    {
        'id': str,
        'title': str,
        'order_in_unit': int
    },
    None  # oder error_message
)
```

**Verwendung:** Erstellt einen neuen Abschnitt in einer Lerneinheit

---

### update_section_materials()
**Parameter:**
- `section_id: str` - UUID des Abschnitts
- `materials: list` - Liste von Material-Objekten

**Material-Objekt:**
```python
{
    'type': 'link' | 'file' | 'markdown' | 'applet',
    'title': str,
    'content': str,  # URL, Markdown oder Dateipfad
    'path': str,     # optional, für type='file'
    'mime_type': str # optional, für type='file'
}
```

**Erwartete Ausgabe:**
```python
(True, None)  # bei Erfolg
(False, error_message)  # bei Fehler
```

**Verwendung:** Aktualisiert die Materialien eines Abschnitts

---

### get_student_courses()
**Parameter:**
- `student_id: str` - UUID des Schülers

**Erwartete Ausgabe:**
```python
(
    [
        {
            'id': str,
            'name': str,
            'created_by': str
        }
    ],
    None  # oder error_message
)
```

**Verwendung:** Lädt alle Kurse, in denen ein Schüler eingeschrieben ist

---

### get_course_students()
**Parameter:**
- `course_id: str` - UUID des Kurses

**Erwartete Ausgabe:**
```python
(
    [
        {
            'id': str,
            'email': str,
            'display_name': str,
            'last_activity': str  # optional
        }
    ],
    None  # oder error_message
)
```

**Verwendung:** Lädt alle Schüler eines Kurses für Live-Übersicht

---

### is_teacher_authorized_for_course()
**Parameter:**
- `teacher_id: str` - UUID des Lehrers
- `course_id: str` - UUID des Kurses

**Erwartete Ausgabe:**
```python
(True/False, None)  # Boolean result
(None, error_message)  # bei Fehler
```

**Verwendung:** Prüft, ob ein Lehrer für einen Kurs autorisiert ist

---

## 10. Task Management Funktionen

### create_regular_task()
**Parameter:**
- `section_id: str` - UUID des Abschnitts
- `title: str` - Aufgabentitel
- `prompt: str` - Aufgabenstellung
- `max_attempts: int` - Maximale Versuche
- `grading_criteria: str` - Bewertungskriterien

**Erwartete Ausgabe:**
```python
(
    {
        'id': str,
        'title': str,
        'order_in_section': int
    },
    None  # oder error_message
)
```

**Verwendung:** Erstellt eine reguläre Aufgabe

---

### create_mastery_task()
**Parameter:**
- `section_id: str` - UUID des Abschnitts
- `title: str` - Aufgabentitel
- `prompt: str` - Aufgabenstellung
- `difficulty_level: int` - Schwierigkeitsgrad (1-5)
- `concept_explanation: str` - Konzepterklärung

**Erwartete Ausgabe:**
```python
(
    {
        'id': str,
        'title': str,
        'order_in_section': int
    },
    None  # oder error_message
)
```

**Verwendung:** Erstellt eine Mastery-Aufgabe für adaptives Lernen

---

### create_task_in_new_structure()
**Parameter:**
- `section_id: str` - UUID des Abschnitts
- `title: str` - Aufgabentitel
- `task_type: str` - 'regular' oder 'mastery'
- `task_data: dict` - Aufgaben-spezifische Daten

**Erwartete Ausgabe:**
```python
(
    {
        'id': str,
        'title': str,
        'task_type': str,
        'order_in_section': int
    },
    None  # oder error_message
)
```

**Verwendung:** Router-Funktion für Task-Erstellung

---

### update_task_in_new_structure()
**Parameter:**
- `task_id: str` - UUID der Aufgabe
- `title: str` - Neuer Titel
- `task_data: dict` - Neue Aufgaben-Daten

**Erwartete Ausgabe:**
```python
(True, None)  # bei Erfolg
(False, error_message)  # bei Fehler
```

**Verwendung:** Aktualisiert eine Aufgabe

---

### delete_task_in_new_structure()
**Parameter:**
- `task_id: str` - UUID der Aufgabe

**Erwartete Ausgabe:**
```python
(True, None)  # bei Erfolg
(False, error_message)  # bei Fehler
```

**Verwendung:** Löscht eine Aufgabe

---

### get_tasks_for_section()
**Parameter:**
- `section_id: str` - UUID des Abschnitts

**Erwartete Ausgabe:**
```python
(
    [
        {
            'id': str,
            'title': str,
            'task_type': str,
            'order_in_section': int,
            'prompt': str,
            # Weitere task-spezifische Felder
        }
    ],
    None  # oder error_message
)
```

**Verwendung:** Lädt alle Aufgaben eines Abschnitts

---

### get_regular_tasks_for_section()
**Parameter:**
- `section_id: str` - UUID des Abschnitts

**Erwartete Ausgabe:**
```python
(
    [
        {
            'id': str,
            'title': str,
            'prompt': str,
            'max_attempts': int,
            'grading_criteria': str,
            'order_in_section': int
        }
    ],
    None  # oder error_message
)
```

**Verwendung:** Lädt nur reguläre Aufgaben eines Abschnitts

---

### get_mastery_tasks_for_section()
**Parameter:**
- `section_id: str` - UUID des Abschnitts

**Erwartete Ausgabe:**
```python
(
    [
        {
            'id': str,
            'title': str,
            'prompt': str,
            'difficulty_level': int,
            'concept_explanation': str,
            'order_in_section': int
        }
    ],
    None  # oder error_message
)
```

**Verwendung:** Lädt nur Mastery-Aufgaben eines Abschnitts

---

### get_section_tasks()
**Parameter:**
- `section_id: str` - UUID des Abschnitts

**Erwartete Ausgabe:**
```python
(
    [
        {
            'id': str,
            'order_in_section': int,
            'title': str
        }
    ],
    None  # oder error_message
)
```

**Verwendung:** Lädt minimale Task-Liste für Übersicht

---

### move_task_up()
**Parameter:**
- `task_id: str` - UUID der Aufgabe

**Erwartete Ausgabe:**
```python
(True, None)  # bei Erfolg
(False, error_message)  # bei Fehler
```

**Verwendung:** Verschiebt Aufgabe eine Position nach oben

---

### move_task_down()
**Parameter:**
- `task_id: str` - UUID der Aufgabe

**Erwartete Ausgabe:**
```python
(True, None)  # bei Erfolg
(False, error_message)  # bei Fehler
```

**Verwendung:** Verschiebt Aufgabe eine Position nach unten

---

## 11. Submission & Progress Funktionen

### update_submission_ai_results()
**Parameter:**
- `submission_id: str` - UUID der Einreichung
- `ai_feedback: str` - KI-generiertes Feedback
- `ai_grade: float` - KI-Note (0-100)
- `is_correct: bool` - Ob die Antwort korrekt ist

**Erwartete Ausgabe:**
```python
(True, None)  # bei Erfolg
(False, error_message)  # bei Fehler
```

**Verwendung:** Aktualisiert Submission mit KI-Bewertung

---

### get_submissions_for_course_and_unit()
**Parameter:**
- `course_id: str` - UUID des Kurses
- `unit_id: str` - UUID der Lerneinheit

**Erwartete Ausgabe:**
```python
(
    [
        {
            'id': str,
            'student_id': str,
            'task_id': str,
            'submission_text': str,
            'submitted_at': str,
            'is_correct': bool,
            'ai_grade': float
        }
    ],
    None  # oder error_message
)
```

**Verwendung:** Lädt alle Submissions für eine Lerneinheit im Kurs

---

### calculate_learning_streak()
**Parameter:**
- `student_id: str` - UUID des Schülers

**Erwartete Ausgabe:**
```python
(
    {
        'current_streak': int,  # Aktuelle Serie in Tagen
        'longest_streak': int,  # Längste Serie
        'last_activity': str    # Letzte Aktivität
    },
    None  # oder error_message
)
```

**Verwendung:** Berechnet Lern-Serien für Gamification

---

## 12. Mastery Learning Funktionen

### get_mastery_tasks_for_course()
**Parameter:**
- `course_id: str` - UUID des Kurses
- `student_id: str` - UUID des Schülers

**Erwartete Ausgabe:**
```python
(
    [
        {
            'id': str,
            'title': str,
            'prompt': str,
            'difficulty_level': int,
            'next_due': str,
            'mastery_score': float,
            'completed_count': int
        }
    ],
    None  # oder error_message
)
```

**Verwendung:** Lädt alle Mastery-Aufgaben mit Fortschritt

---

### get_next_due_mastery_task()
**Parameter:**
- `student_id: str` - UUID des Schülers
- `course_id: str` - UUID des Kurses

**Erwartete Ausgabe:**
```python
(
    {
        'id': str,
        'title': str,
        'prompt': str,
        'difficulty_level': int,
        'concept_explanation': str,
        'last_attempt': str
    },
    None  # oder error_message
)
```

**Verwendung:** Lädt nächste fällige Mastery-Aufgabe

---

### save_mastery_submission()
**Parameter:**
- `student_id: str` - UUID des Schülers
- `task_id: str` - UUID der Aufgabe
- `answer_text: str` - Antwort des Schülers
- `ai_feedback: str` - KI-Feedback
- `is_correct: bool` - Ob korrekt
- `confidence_score: float` - Konfidenz-Score

**Erwartete Ausgabe:**
```python
(
    {
        'id': str,
        'created_at': str
    },
    None  # oder error_message
)
```

**Verwendung:** Speichert Mastery-Submission mit Bewertung

---

### submit_mastery_answer()
**Parameter:**
- `student_id: str` - UUID des Schülers
- `task_id: str` - UUID der Aufgabe
- `answer_text: str` - Antwort des Schülers

**Erwartete Ausgabe:**
```python
(
    {
        'submission_id': str,
        'is_correct': bool,
        'ai_feedback': str,
        'next_review': str
    },
    None  # oder error_message
)
```

**Verwendung:** Vollständiger Mastery-Submit-Workflow

---

### get_mastery_stats_for_student()
**Parameter:**
- `student_id: str` - UUID des Schülers
- `course_id: str` - UUID des Kurses

**Erwartete Ausgabe:**
```python
(
    {
        'total_mastery_tasks': int,
        'mastered_count': int,
        'in_progress_count': int,
        'average_mastery_score': float,
        'total_attempts': int
    },
    None  # oder error_message
)
```

**Verwendung:** Lädt Mastery-Statistiken für Schüler

---

### get_mastery_overview_for_teacher()
**Parameter:**
- `course_id: str` - UUID des Kurses

**Erwartete Ausgabe:**
```python
(
    [
        {
            'student_id': str,
            'student_name': str,
            'mastered_count': int,
            'in_progress_count': int,
            'average_score': float
        }
    ],
    None  # oder error_message
)
```

**Verwendung:** Lädt Mastery-Übersicht aller Schüler für Lehrer

---

## Session Management

Alle Funktionen nutzen intern `get_session_id()` für die Authentifizierung. Die Session-ID wird aus `st.session_state.auth_session_id` gelesen.

## Fehlerbehandlung

Alle Funktionen folgen dem Muster:
```python
result, error = function_name(params)
if error:
    # Handle error
else:
    # Use result
```

## Bekannte Probleme

1. **get_submission_status_matrix** gibt 0 sections zurück, obwohl sections existieren
2. **get_all_feedback** Schema-Inkompatibilitäten möglich
3. Session-basierte Authentifizierung erfordert gültigen HttpOnly Cookie