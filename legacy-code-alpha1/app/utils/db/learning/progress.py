"""Progress tracking functions for HttpOnly Cookie support.

This module contains all progress and submission status tracking functions
that have been migrated to use the RPC pattern with session-based authentication.
"""

import json
import traceback
import streamlit as st
from typing import Optional, Dict, Any, List, Tuple

from ..core.session import get_session_id, get_anon_client, handle_rpc_result


def get_submission_status_matrix(course_id: str, unit_id: str, force_refresh: bool = False) -> tuple[dict | None, str | None]:
    """Holt die komplette Matrix-Ansicht für die Live-Übersicht.
    
    Args:
        course_id: ID des Kurses
        unit_id: ID der Lerneinheit
        force_refresh: Wenn True, umgeht den Cache und lädt frische Daten
    
    Returns:
        tuple: (Dictionary mit Struktur für Matrix-View, None) bei Erfolg, (None, Fehlermeldung) bei Fehler.
    """
    if not course_id or not unit_id:
        return None, "Kurs-ID und Einheiten-ID sind erforderlich."
    
    if force_refresh:
        return _get_submission_status_matrix_uncached(course_id, unit_id)
    else:
        # Cache-Key mit Timestamp für manuelle Invalidierung
        import time
        cache_key = f"{course_id}_{unit_id}_{int(time.time() // 60)}"  # Ändert sich jede Minute
        return _get_submission_status_matrix_cached(course_id, unit_id, cache_key)


def _get_submission_status_matrix_cached(course_id: str, unit_id: str, cache_key: str) -> tuple[dict | None, str | None]:
    """Cached Version mit Streamlit Session State."""
    if 'submission_matrix_cache' not in st.session_state:
        st.session_state.submission_matrix_cache = {}
    
    # Check cache
    if cache_key in st.session_state.submission_matrix_cache:
        return st.session_state.submission_matrix_cache[cache_key], None
    
    # Load fresh data
    result, error = _get_submission_status_matrix_uncached(course_id, unit_id)
    if result and not error:
        st.session_state.submission_matrix_cache[cache_key] = result
    
    return result, error


def _get_submission_status_matrix_uncached(course_id: str, unit_id: str) -> tuple[dict | None, str | None]:
    """Interne Implementierung ohne Cache."""
    if not course_id or not unit_id:
        return None, "Kurs-ID und Einheiten-ID sind erforderlich."
    
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        
        # Hole zuerst die Matrix-Daten von der SQL-Funktion
        result = client.rpc('_get_submission_status_matrix_uncached', {
            'p_session_id': session_id,
            'p_course_id': course_id,
            'p_unit_id': unit_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Abrufen der Submission-Matrix')
            print(f"RPC error in _get_submission_status_matrix_uncached: {error_msg}")
            return None, error_msg
            
        if not hasattr(result, 'data') or result.data is None:
            print("No data returned from _get_submission_status_matrix_uncached RPC")
            return None, "Keine Daten von der Datenbank erhalten."
        
        # Die SQL-Funktion gibt jetzt ein JSONB-Objekt zurück mit students, tasks und submissions
        matrix_data = result.data if isinstance(result.data, dict) else {}
        
        print(f"Got matrix data with {len(matrix_data.get('students', []))} students")
        
        # Hole zusätzlich die Sections für die Unit
        sections_result = client.rpc('get_unit_sections', {
            'p_session_id': session_id,
            'p_unit_id': unit_id
        }).execute()
        
        if hasattr(sections_result, 'error') and sections_result.error:
            print(f"Error getting sections: {sections_result.error}")
            sections = []
        else:
            sections = sections_result.data if hasattr(sections_result, 'data') else []
        
        print(f"Got {len(sections)} sections for unit {unit_id}")
        
        # Extrahiere Daten aus der JSONB-Struktur
        students = matrix_data.get('students', [])
        tasks = matrix_data.get('tasks', [])
        submissions_data = matrix_data.get('submissions', {})
        
        # Baue die erwartete Struktur auf
        matrix_structure = {
            'students': [],
            'sections': [],
            'total_tasks': len(tasks),
            'total_submissions': 0
        }
        
        # Verarbeite Studenten
        for student in students:
            student_info = {
                'student_id': student.get('id'),
                'display_name': student.get('name', 'Unbekannt'),
                'email': student.get('name', 'Unbekannt')  # Name contains email or full_name
            }
            matrix_structure['students'].append(student_info)
        
        # Organisiere Tasks nach Sections
        section_tasks = {}
        for task in tasks:
            section_id = task.get('section_id')
            if section_id not in section_tasks:
                section_tasks[section_id] = []
            section_tasks[section_id].append(task)
        
        # Verarbeite Sections
        for section in sections:
            section_id = section.get('id')
            
            section_data = {
                'id': section_id,
                'title': section.get('title', 'Unbenannt'),
                'order': section.get('order_in_unit', 0),
                'tasks': [],
                'submissions': {}
            }
            
            # Füge Tasks zur Section hinzu
            if section_id in section_tasks:
                for task in section_tasks[section_id]:
                    task_data = {
                        'id': task.get('id'),
                        'title': task.get('title', 'Unbenannt'),
                        'instruction': task.get('title', ''),  # title contains instruction
                        'order_in_section': 0  # Not provided by SQL function
                    }
                    section_data['tasks'].append(task_data)
            
            # Füge Submission-Daten für jeden Studenten hinzu
            for student in students:
                student_id = str(student.get('id'))
                
                if student_id not in section_data['submissions']:
                    section_data['submissions'][student_id] = {}
                
                # Hole submissions für diesen Studenten
                student_submissions = submissions_data.get(student_id, {})
                
                # Verarbeite jeden Task in dieser Section
                for task in section_data['tasks']:
                    task_id = str(task['id'])
                    if task_id in student_submissions:
                        submission_info = student_submissions[task_id]
                        if submission_info.get('has_submission'):
                            matrix_structure['total_submissions'] += 1
                            section_data['submissions'][student_id][task_id] = {
                                'status': 'submitted',
                                'is_correct': submission_info.get('is_correct', False),
                                'has_feedback': bool(submission_info.get('latest_submission_id')),
                                'submission_count': 1,  # Not tracked in new structure
                                'latest_submission_at': None  # Not provided
                            }
                        else:
                            section_data['submissions'][student_id][task_id] = {
                                'status': 'not_submitted'
                            }
                    else:
                        section_data['submissions'][student_id][task_id] = {
                            'status': 'not_submitted'
                        }
            
            matrix_structure['sections'].append(section_data)
        
        print(f"Final structure: {len(matrix_structure['sections'])} sections, {matrix_structure['total_tasks']} tasks, {matrix_structure['total_submissions']} submissions")
        
        return matrix_structure, None
        
    except Exception as e:
        print(f"Error in _get_submission_status_matrix_uncached: {traceback.format_exc()}")
        return None, f"Fehler: {str(e)}"


def get_submissions_for_course_and_unit(course_id: str, unit_id: str) -> tuple[list | None, str | None]:
    """Holt alle Einreichungen für eine Lerneinheit in einem Kurs mit vollständigen Details.
    
    Returns:
        tuple: (Liste von Submissions mit Student/Task-Info, None) bei Erfolg, (None, Fehlermeldung) bei Fehler.
    """
    if not course_id or not unit_id:
        return None, "Kurs-ID und Einheiten-ID sind erforderlich."
    
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('get_submissions_for_course_and_unit', {
            'p_session_id': session_id,
            'p_course_id': course_id,
            'p_unit_id': unit_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Abrufen der Einreichungen')
            return None, error_msg
            
        if hasattr(result, 'data'):
            # Map fields from RPC response to expected format
            submissions = []
            for sub in (result.data or []):
                submission = {
                    'id': sub.get('submission_id'),
                    'student_id': sub.get('student_id'),
                    'student_name': sub.get('student_name'),
                    'student_email': sub.get('student_email'),
                    'task_id': sub.get('task_id'),
                    'task_title': sub.get('task_title', 'Aufgabe'),
                    'section_title': sub.get('section_title', 'Unbekannter Abschnitt'),
                    'submission_data': json.loads(sub.get('submission_text', '{}')) if sub.get('submission_text') else None,
                    'submitted_at': sub.get('submitted_at'),
                    'ai_feedback': sub.get('ai_feedback'),
                    'ai_grade': sub.get('ai_grade'),
                    'is_correct': sub.get('is_correct'),
                    'teacher_feedback': sub.get('teacher_feedback'),
                    'override_grade': sub.get('override_grade'),
                    'attempt_number': sub.get('attempt_number', 1)
                }
                submissions.append(submission)
            return submissions, None
        
        return None, "Unerwartete Antwort beim Abrufen der Einreichungen."
        
    except Exception as e:
        print(f"Error in get_submissions_for_course_and_unit: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Einreichungen: {str(e)}"


def calculate_learning_streak(student_id: str) -> tuple[int, str | None]:
    """Berechnet die aktuelle Lern-Serie (aufeinanderfolgende Tage mit Aktivität).
    
    Die Funktion zählt die Anzahl aufeinanderfolgender Tage, an denen der Schüler
    mindestens eine Einreichung gemacht hat, beginnend vom heutigen oder gestrigen Tag.
    
    Args:
        student_id: ID des Schülers
        
    Returns:
        tuple: (streak_days, error_message)
            - streak_days: Anzahl der aufeinanderfolgenden Lerntage (0 wenn keine Aktivität)
            - error_message: Fehlermeldung oder None bei Erfolg
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return 0, "Keine aktive Session gefunden"
        
        if not student_id:
            return 0, "Student-ID ist erforderlich"
        
        client = get_anon_client()
        result = client.rpc('calculate_learning_streak', {
            'p_session_id': session_id,
            'p_student_id': student_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Berechnen der Lern-Serie')
            print(f"Error in calculate_learning_streak: {error_msg}")
            return 0, error_msg
        
        # SQL function returns a table with current_streak, longest_streak, last_activity_date
        if result.data is not None and isinstance(result.data, list) and len(result.data) > 0:
            row = result.data[0]
            current_streak = row.get('current_streak', 0)
            return current_streak, None
        
        return 0, None
        
    except Exception as e:
        print(f"Error in calculate_learning_streak: {traceback.format_exc()}")
        return 0, f"Fehler beim Berechnen der Lern-Serie: {str(e)}"