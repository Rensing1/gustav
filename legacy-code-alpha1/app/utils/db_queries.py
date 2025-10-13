# app/utils/db_queries.py

import sys
import os
import json

# Füge das übergeordnete Verzeichnis (app) zum Python-Pfad hinzu
# damit absolute Imports wie \'from ai.service...\' funktionieren
current_dir = os.path.dirname(os.path.abspath(__file__)) # Pfad zu /app/utils
app_dir = os.path.dirname(current_dir) # Pfad zu /app
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# --- Normale Imports danach --- 
from utils.session_client import get_user_supabase_client, get_service_supabase_client, get_anon_supabase_client
from supabase import PostgrestAPIResponse
import streamlit as st
from datetime import datetime, timezone, date, timedelta
import traceback
import random
from typing import Dict, List, Optional, Tuple

# =====================================================
# HttpOnly Cookie Support - Session-based DB Functions
# =====================================================

# Import session functions from new module
from .db.core.session import get_session_id, get_anon_client, handle_rpc_result
# Import platform functions from new module
from .db.platform.feedback import submit_feedback, get_all_feedback
# Import enrollment functions from new module
from .db.courses.enrollment import get_published_section_details_for_student
# Import mastery functions from new module
from .db.learning.mastery import (
    get_mastery_tasks_for_course,
    get_next_due_mastery_task,
    get_next_mastery_task_or_unviewed_feedback,
    get_mastery_stats_for_student,
    get_mastery_progress_summary
)
# Import progress functions from new module  
from .db.learning.progress import (
    get_submission_status_matrix,
    _get_submission_status_matrix_cached,
    _get_submission_status_matrix_uncached,
    get_submissions_for_course_and_unit,
    calculate_learning_streak
)
# Import submission functions from new module
from .db.learning.submissions import (
    create_submission,
    get_submission_by_id,
    get_submission_history,
    mark_feedback_as_viewed_safe,
    get_submission_queue_position
)

# Mastery imports moved to function level to avoid import conflicts
#from ai.feedback import CombinedMasteryFeedbackModule
#from mastery.mastery_config import INITIAL_DIFFICULTY, STABILITY_GROWTH_FACTOR
#from utils.mastery_algorithm import calculate_next_review_state

# Phase 4: Task Type Separation completed - feature flag removed

# --- Helper Functions for Task Type Separation ---

def _get_task_table_name() -> str:
    """
    Returns the table name to use for task operations.
    During migration, we use 'task' (old structure).
    After migration, this could switch to views or new tables.
    """
    if is_task_separation_enabled():
        # Phase 1: Views are available, but we still use old table for writes
        return 'task'  # Will be changed in later phases
    return 'task'

# Import from modularized structure
from .db.content.tasks import create_regular_task


# Import from modularized structure
from .db.content.tasks import create_mastery_task, get_task_details


# Legacy function for backward compatibility - DEPRECATED
# Import from working module to replace broken implementation
from .db.content import create_task_in_new_structure

# Import from working module to replace broken implementation
from .db.content import update_task_in_new_structure

# Import from working module to replace broken implementation
from .db.content import delete_task_in_new_structure

# Phase 4: Removed helper functions - now using views directly
# Views provide consistent interface regardless of migration state

def get_regular_tasks_table_name() -> str:
    """
    Returns the view name for regular tasks (Phase 4: Always use views).
    """
    return 'all_regular_tasks'

def get_mastery_tasks_table_name() -> str:
    """
    Returns the view name for mastery tasks (Phase 4: Always use views).
    """
    return 'all_mastery_tasks'

# Note: Filter functions removed in Phase 4 - views handle filtering automatically
    if not is_task_separation_enabled():
        # Add filter for mastery tasks
        return query.eq('is_mastery', True)
    return query  # No filter needed when using view


# --- Kurs-bezogene Abfragen --- 

# Import from working module
from .db.courses import get_courses_by_creator


# Import from working module  
from .db.courses import create_course

def _legacy_create_course(name: str, creator_id: str = None) -> tuple[dict | None, str | None]:
    """Erstellt einen neuen Kurs über PostgreSQL Function (HttpOnly Cookie Support)"""
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"

        if not name:
            return None, "Kursname ist erforderlich."

        client = get_anon_client()
        result = client.rpc('create_course', {
            'p_session_id': session_id,
            'p_name': name
        }).execute()

        data, error = handle_rpc_result(result, [])
        if error:
            return None, error
        
        # PostgreSQL Function gibt ein Array zurück, wir wollen das erste Element
        if data and len(data) > 0:
            course_data = data[0]
            if course_data.get('success'):
                return {
                    'id': course_data.get('id'),
                    'name': course_data.get('name'),
                    'created_at': course_data.get('created_at')
                }, None
            else:
                return None, course_data.get('error_message', 'Unbekannter Fehler')
        
        return None, "Keine Daten von der Datenbank erhalten"
    
    except Exception as e:
        print(f"Error in create_course: {traceback.format_exc()}")
        return None, f"Fehler beim Erstellen des Kurses: {str(e)}"


# --- Nutzer-bezogene Abfragen ---

# Import from working module to replace broken implementation
from .db.core.auth import get_users_by_role

# Import from working module
from .db.courses import get_students_in_course

# Import from working module
from .db.courses import get_teachers_in_course

# Import from working module to replace broken implementation
from .db.courses import add_user_to_course

# Import from working module to replace broken implementation
from .db.courses import remove_user_from_course


# --- Lerneinheit-Kurs-Zuweisungs-Abfragen ---

def get_courses_assigned_to_unit(unit_id: str) -> tuple[list | None, str | None]:
    """Holt die IDs und Namen der Kurse, denen eine Lerneinheit zugewiesen ist.

    Returns:
        tuple: (Liste der zugewiesenen Kurse [{'id': ..., 'name': ...}], None) bei Erfolg,
               (None, Fehlermeldung) bei Fehler.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return [], "Keine aktive Session gefunden"
        
        if not unit_id:
            return [], None
        
        client = get_anon_client()
        result = client.rpc('get_courses_assigned_to_unit', {
            'p_session_id': session_id,
            'p_unit_id': unit_id
        }).execute()
        
        data, error = handle_rpc_result(result, [])
        if error:
            return None, error
        
        # Map course_id and course_name to expected format
        courses = []
        for course in data:
            courses.append({
                'id': course.get('course_id'),
                'name': course.get('course_name')
            })
        
        return courses, None
    except Exception as e:
        import traceback
        print(f"Error in get_courses_assigned_to_unit: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Kurse: {str(e)}"

def assign_unit_to_course(unit_id: str, course_id: str) -> tuple[bool, str | None]:
    """Weist eine Lerneinheit einem Kurs zu.

    Returns:
        tuple: (True, None) bei Erfolg oder wenn bereits vorhanden, (False, Fehlermeldung) bei Fehler.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        if not unit_id or not course_id:
            return False, "Lerneinheit-ID und Kurs-ID sind erforderlich."
        
        client = get_anon_client()
        result = client.rpc('assign_unit_to_course', {
            'p_session_id': session_id,
            'p_unit_id': unit_id,
            'p_course_id': course_id
        }).execute()
        
        # RPC returns void on success, raises exception on error
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Zuweisen der Lerneinheit')
            return False, error_msg
        
        return True, None
    except Exception as e:
        import traceback
        print(f"Error in assign_unit_to_course: {traceback.format_exc()}")
        return False, f"Fehler beim Zuweisen der Lerneinheit: {str(e)}"

def unassign_unit_from_course(unit_id: str, course_id: str) -> tuple[bool, str | None]:
    """Entfernt die Zuweisung einer Lerneinheit von einem Kurs.

    Returns:
        tuple: (True, None) bei Erfolg, (False, Fehlermeldung) bei Fehler.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        if not unit_id or not course_id:
            return False, "Lerneinheit-ID und Kurs-ID sind erforderlich."
        
        client = get_anon_client()
        result = client.rpc('unassign_unit_from_course', {
            'p_session_id': session_id,
            'p_unit_id': unit_id,
            'p_course_id': course_id
        }).execute()
        
        # RPC returns void on success, raises exception on error
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Entfernen der Zuweisung')
            return False, error_msg
        
        return True, None
    except Exception as e:
        import traceback
        print(f"Error in unassign_unit_from_course: {traceback.format_exc()}")
        return False, f"Fehler beim Entfernen der Zuweisung: {str(e)}"

# --- Abschnitt-bezogene Abfragen ---

# Import from working module to replace broken implementation
from .db.content import get_sections_for_unit

# --- Abfragen für Lerneinheit-Kurs-Beziehung ---

def get_assigned_units_for_course(course_id: str) -> tuple[list | None, str | None]:
    """Holt die Lerneinheiten über PostgreSQL Function.

    Returns:
        tuple: (Liste der Einheiten [{'learning_unit_id': ..., 'learning_unit_title': ...}], None) bei Erfolg,
               (None, Fehlermeldung) bei Fehler.
    """
    if not course_id: return [], None
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"

        client = get_anon_client()
        result = client.rpc('get_course_units', {
            'p_session_id': session_id,
            'p_course_id': course_id
        }).execute()

        data, error = handle_rpc_result(result, [])
        if error:
            return None, error
        
        # Transform data to match expected format
        assigned_units = [{
            'id': item['learning_unit_id'],
            'title': item['learning_unit_title']
        } for item in data]
        
        # Sortiere nach Titel für die Selectbox
        assigned_units.sort(key=lambda x: x.get('title', ''))
        return assigned_units, None

    except Exception as e:
        error_msg = f"Unerwarteter Python-Fehler beim Abrufen der Einheiten für Kurs {course_id}: {e}"
        print(f"Exception in get_assigned_units_for_course: {e}")
        return None, error_msg


# --- Abfragen für Abschnitt-Freigabe ---

def get_section_statuses_for_unit_in_course(unit_id: str, course_id: str) -> tuple[dict | None, str | None]:
    """Holt den Veröffentlichungsstatus ({section_id: is_published}) für alle Abschnitte
       einer Einheit innerhalb eines bestimmten Kurses.

    Returns:
        tuple: (Dictionary {section_id: bool}, None) bei Erfolg, (None, Fehlermeldung) bei Fehler.
    """
    if not unit_id or not course_id: 
        return {}, None # Leeres Dict ist gültig
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('get_section_statuses_for_unit_in_course', {
            'p_session_id': session_id,
            'p_unit_id': unit_id,
            'p_course_id': course_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = f"Fehler beim Abrufen der Abschnitt-Status: {result.error.get('message', 'Datenbankfehler')}"
            return None, error_msg
            
        if hasattr(result, 'data'):
            # Convert result to dict format {section_id: is_published}
            status_dict = {}
            for item in (result.data or []):
                status_dict[item['section_id']] = item['is_published']
            return status_dict, None
        
        return None, "Unerwartete Antwort beim Abrufen der Abschnitt-Status."
        
    except Exception as e:
        import traceback
        print(f"Error in get_section_statuses_for_unit_in_course: {traceback.format_exc()}")
        return None, f"Fehler: {str(e)}"

def publish_section_for_course(section_id: str, course_id: str) -> tuple[bool, str | None]:
    """Veröffentlicht einen Abschnitt für einen Kurs (setzt is_published=true)."""
    if not section_id or not course_id: 
        return False, "Abschnitt-ID und Kurs-ID erforderlich."
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('publish_section_for_course', {
            'p_session_id': session_id,
            'p_section_id': section_id,
            'p_course_id': course_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Veröffentlichen')
            return False, error_msg
            
        return True, None
        
    except Exception as e:
        import traceback
        print(f"Error in publish_section_for_course: {traceback.format_exc()}")
        return False, f"Fehler: {str(e)}"

def unpublish_section_for_course(section_id: str, course_id: str) -> tuple[bool, str | None]:
    """Zieht die Veröffentlichung eines Abschnitts für einen Kurs zurück (setzt is_published=false)."""
    if not section_id or not course_id: 
        return False, "Abschnitt-ID und Kurs-ID erforderlich."
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('unpublish_section_for_course', {
            'p_session_id': session_id,
            'p_section_id': section_id,
            'p_course_id': course_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Zurückziehen')
            return False, error_msg
            
        return True, None
        
    except Exception as e:
        import traceback
        print(f"Error in unpublish_section_for_course: {traceback.format_exc()}")
        return False, f"Fehler: {str(e)}"

def get_user_course_ids(student_id: str) -> list[str]:
    """Holt nur die Kurs-IDs in denen ein Schüler eingeschrieben ist.
    
    Für Memory-Management und Session-State-Cleanup.
    
    Returns:
        Liste der Kurs-IDs als Strings
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return []
        
        if not student_id:
            return []
        
        client = get_anon_client()
        result = client.rpc('get_user_course_ids', {
            'p_session_id': session_id,
            'p_student_id': student_id
        }).execute()
        
        data, error = handle_rpc_result(result, [])
        if error:
            print(f"Error in get_user_course_ids: {error}")
            return []
        
        # SQL function returns array of IDs directly
        return data if isinstance(data, list) else []
    except Exception as e:
        import traceback
        print(f"Error in get_user_course_ids: {traceback.format_exc()}")
        return []


def get_student_courses(student_id: str) -> tuple[list | None, str | None]:
    """Holt die Kurse (id, name), in denen ein Schüler eingeschrieben ist.

    Returns:
        tuple: (Liste der Kurse [{'id': ..., 'name': ...}], None) bei Erfolg,
               (None, Fehlermeldung) bei Fehler.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return [], "Keine aktive Session gefunden"
        
        if not student_id:
            return [], None
        
        client = get_anon_client()
        result = client.rpc('get_student_courses', {
            'p_session_id': session_id,
            'p_student_id': student_id
        }).execute()
        
        data, error = handle_rpc_result(result, [])
        if error:
            return None, error
        
        # Data from RPC is already in correct format: id, name, creator_id, created_at
        # Just ensure sorting by name with None-safe handling
        courses = sorted(data, key=lambda x: (x.get('name') or ''))
        
        return courses, None
    except Exception as e:
        import traceback
        print(f"Error in get_student_courses: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Kurse: {str(e)}"

# create_submission is now imported from .db.learning.submissions

def get_submission_history(student_id: str, task_id: str) -> tuple[list | None, str | None]:
    """Holt alle Einreichungen eines Schülers für eine Aufgabe, sortiert nach attempt_number."""
    try:
        session_id = get_session_id()
        if not session_id:
            return [], "Keine aktive Session gefunden"
        
        if not student_id or not task_id:
            return None, "Student-ID und Task-ID sind erforderlich."
        
        client = get_anon_client()
        result = client.rpc('get_submission_history', {
            'p_session_id': session_id,
            'p_student_id': student_id,
            'p_task_id': task_id
        }).execute()
        
        return handle_rpc_result(result, [])
    except Exception as e:
        import traceback
        print(f"Error in get_submission_history: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Historie: {str(e)}"

# get_remaining_attempts is imported from .db.learning.submissions

# --- Funktionen für KI-Verarbeitung ---

# get_task_details is imported from .db.content.tasks


def update_submission_ai_results(
    submission_id: str, 
    criteria_analysis: str | None, 
    feedback: str | None, 
    rating_suggestion: str | None,
    feed_back_text: str | None = None,
    feed_forward_text: str | None = None
) -> tuple[bool, str | None]:
    """Aktualisiert eine Einreichung mit den Ergebnissen der KI.
       Verwendet die erweiterte RPC-Funktion für alle Felder.
       
       Args:
           submission_id: ID der Einreichung
           criteria_analysis: JSON-String der Kriterien-Analyse
           feedback: Kombiniertes Feedback (für Abwärtskompatibilität)
           rating_suggestion: Bewertungsvorschlag
           feed_back_text: Feed-Back Teil (Wo stehe ich?)
           feed_forward_text: Feed-Forward Teil (Nächste Schritte)
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        if not submission_id:
            return False, "Submission-ID fehlt."
        
        # Determine is_correct based on rating_suggestion
        is_correct = False
        if rating_suggestion and rating_suggestion.lower() in ['korrekt', 'richtig', 'correct', 'true']:
            is_correct = True
        
        # Use combined feedback or separate feed_back/feed_forward
        ai_feedback_text = feedback
        if not ai_feedback_text and (feed_back_text or feed_forward_text):
            parts = []
            if feed_back_text:
                parts.append(f"**Wo du stehst:**\n{feed_back_text}")
            if feed_forward_text:
                parts.append(f"**Nächste Schritte:**\n{feed_forward_text}")
            ai_feedback_text = "\n\n".join(parts)
        
        # Use extended RPC function that handles all fields
        client = get_anon_client()
        result = client.rpc('update_submission_ai_results_extended', {
            'p_session_id': session_id,
            'p_submission_id': submission_id,
            'p_is_correct': is_correct,
            'p_ai_feedback': ai_feedback_text,
            'p_criteria_analysis': criteria_analysis,
            'p_ai_grade': rating_suggestion,
            'p_feed_back_text': feed_back_text,
            'p_feed_forward_text': feed_forward_text
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = f"DB Fehler beim Aktualisieren der AI-Ergebnisse für Submission {submission_id}: {result.error.get('message', 'Unbekannter Fehler')}"
            print(error_msg)
            return False, error_msg
        
        return True, None
        
    except Exception as e:
        import traceback
        print(f"Exception in update_submission_ai_results: {traceback.format_exc()}")
        return False, f"Python Fehler beim Aktualisieren der AI-Ergebnisse für Submission {submission_id}: {e}"

def get_submission_by_id(submission_id: str) -> tuple[dict | None, str | None]:
    """Holt eine einzelne Einreichung mit allen Details.
    
    Returns:
        tuple: (Submission-Dict, None) bei Erfolg, (None, Fehlermeldung) bei Fehler.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        if not submission_id:
            return None, "Submission-ID ist erforderlich."
        
        client = get_anon_client()
        result = client.rpc('get_submission_by_id', {
            'p_session_id': session_id,
            'p_submission_id': submission_id
        }).execute()
        
        data, error = handle_rpc_result(result, None)
        if error:
            return None, error
        
        # SQL function returns array, we need single item
        if isinstance(data, list) and len(data) > 0:
            return data[0], None
        elif isinstance(data, dict):
            return data, None
        else:
            return None, "Submission nicht gefunden."
    except Exception as e:
        import traceback
        print(f"Error in get_submission_by_id: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Submission: {str(e)}"

def get_submission_for_task(student_id: str, task_id: str) -> tuple[dict | None, str | None]:
    """Holt die Einreichung eines Schülers für eine bestimmte Aufgabe.
    
    Returns:
        tuple: (Submission-Dict, None) bei Erfolg, (None, Fehlermeldung) bei Fehler oder wenn keine Einreichung existiert.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        if not student_id or not task_id:
            return None, "Student-ID und Task-ID sind erforderlich."
        
        client = get_anon_client()
        result = client.rpc('get_submission_for_task', {
            'p_session_id': session_id,
            'p_student_id': student_id,
            'p_task_id': task_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            return None, f"Fehler beim Abrufen der Submission: {result.error.get('message', 'Unbekannter Fehler')}"
        
        if result.data and len(result.data) > 0:
            return result.data[0], None
        else:
            return None, None  # Keine Einreichung gefunden (kein Fehler)
        
    except Exception as e:
        import traceback
        print(f"Error in get_submission_for_task: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Submission für Student {student_id} und Task {task_id}: {e}"

# --- Live-Übersicht Funktionen ---

def get_course_students(course_id: str) -> tuple[list | None, str | None]:
    """Holt alle Schüler eines Kurses für die Live-Übersicht.
    
    Returns:
        tuple: (Liste mit student_id, full_name, email), None) bei Erfolg, (None, Fehlermeldung) bei Fehler.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        if not course_id:
            return [], None
        
        client = get_anon_client()
        result = client.rpc('get_course_students', {
            'p_session_id': session_id,
            'p_course_id': course_id
        }).execute()
        
        data, error = handle_rpc_result(result, [])
        if error:
            return None, error
        
        # Transform data to expected format
        students = []
        for item in data:
            # RPC returns display_name, we need full_name for compatibility
            full_name = item.get('display_name', '')
            if not full_name or full_name == 'None':
                email = item.get('email', '')
                full_name = email.split('@')[0] if '@' in email else email
            
            students.append({
                'student_id': item.get('student_id'),
                'full_name': full_name,
                'email': item.get('email', '')
            })
        
        # Sort by name
        students.sort(key=lambda x: x['full_name'].lower())
        return students, None
    except Exception as e:
        import traceback
        print(f"Error in get_course_students: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Schüler: {str(e)}"

def get_section_tasks(section_id: str) -> tuple[list | None, str | None]:
    """Holt alle Aufgaben eines Abschnitts.
    
    Returns:
        tuple: (Liste mit task_id, order_in_section, instruction), None) bei Erfolg, (None, Fehlermeldung) bei Fehler.
    """
    if not section_id:
        return [], None
    
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('get_section_tasks', {
            'p_session_id': session_id,
            'p_section_id': section_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Abrufen der Aufgaben')
            return None, error_msg
            
        if hasattr(result, 'data'):
            # Map fields if needed
            tasks = []
            for task in (result.data or []):
                mapped_task = {
                    'id': task.get('id'),
                    'order_in_section': task.get('order_in_section'),
                    'instruction': task.get('title') or task.get('prompt')  # Map title/prompt to instruction
                }
                tasks.append(mapped_task)
            return tasks, None
        
        return None, "Unerwartete Antwort beim Abrufen der Aufgaben."
        
    except Exception as e:
        import traceback
        print(f"Error in get_section_tasks: {traceback.format_exc()}")
        return None, f"Fehler: {str(e)}"

# get_submission_status_matrix and related functions are now imported from .db.learning.progress

# --- Teacher Override Funktionen ---

# update_submission_teacher_override is imported from .db.learning.submissions

# get_submissions_for_course_and_unit is now imported from .db.learning.progress

# --- Lerneinheiten-Funktionen ---

# Import from working module to replace broken implementation
from .db.content import get_learning_units_by_creator

# Import from working module to replace broken implementation
from .db.content import create_learning_unit

# Import from working module to replace broken implementation
from .db.content import update_learning_unit

# Import from working module to replace broken implementation
from .db.content import delete_learning_unit

# Import from working module to replace broken implementation
from .db.content import get_learning_unit_by_id

# --- Abschnitt-Funktionen ---

def create_section(unit_id: str, title: str, order: int) -> tuple[dict | None, str | None]:
    """Erstellt einen neuen Abschnitt in einer Lerneinheit.
    
    Returns:
        tuple: (Neuer Abschnitt, None) bei Erfolg, (None, Fehlermeldung) bei Fehler.
    """
    if not all([unit_id, isinstance(order, int)]): 
        return None, "Unit-ID und Order sind erforderlich."
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('create_section', {
            'p_session_id': session_id,
            'p_unit_id': unit_id,
            'p_title': title if title else f"Abschnitt {order}",
            'p_description': None,
            'p_materials': json.dumps([])  # Convert to JSONB
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Erstellen des Abschnitts')
            return None, error_msg
            
        # RPC returns UUID, build full response
        if result.data:
            return {
                'id': result.data,
                'unit_id': unit_id,
                'title': title if title else f"Abschnitt {order}",
                'order_in_unit': order,
                'materials': []
            }, None
            
        return None, "Unerwartete Antwort beim Erstellen des Abschnitts."
        
    except Exception as e:
        import traceback
        print(f"Error in create_section: {traceback.format_exc()}")
        return None, f"Fehler: {str(e)}"

def update_section_materials(section_id: str, materials: list) -> tuple[bool, str | None]:
    """Aktualisiert die Materialien eines Abschnitts.
    
    Returns:
        tuple: (True, None) bei Erfolg, (False, Fehlermeldung) bei Fehler.
    """
    if not section_id:
        return False, "Section-ID ist erforderlich."
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('update_section_materials', {
            'p_session_id': session_id,
            'p_section_id': section_id,
            'p_materials': json.dumps(materials)  # Convert to JSONB
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Aktualisieren der Materialien')
            return False, error_msg
            
        return True, None
        
    except Exception as e:
        import traceback
        print(f"Error in update_section_materials: {traceback.format_exc()}")
        return False, f"Fehler: {str(e)}"

# --- Aufgaben-Funktionen ---

def get_tasks_for_section(section_id: str) -> tuple[list | None, str | None]:
    """Holt alle Aufgaben eines Abschnitts.
    
    Returns:
        tuple: (Liste der Aufgaben, None) bei Erfolg, (None, Fehlermeldung) bei Fehler.
    """
    if not section_id: 
        return [], None
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('get_tasks_for_section', {
            'p_session_id': session_id,
            'p_section_id': section_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = f"Fehler beim Abrufen der Aufgaben: {result.error.get('message', 'Unbekannter Fehler')}"
            print(f"Fehler in get_tasks_for_section: {result.error}")
            return None, error_msg
        
        if hasattr(result, 'data'):
            # Map fields from RPC response to expected format
            tasks = []
            for task in (result.data or []):
                mapped_task = {
                    'id': task.get('id'),
                    'section_id': task.get('section_id'),
                    'instruction': task.get('title') or task.get('prompt'),  # Map title/prompt to instruction
                    'task_type': task.get('task_type'),
                    'order_in_section': task.get('order_in_section'),
                    'assessment_criteria': task.get('grading_criteria', []),
                    'solution_hints': task.get('concept_explanation'),
                    'is_mastery': task.get('is_mastery', False),
                    'max_attempts': task.get('max_attempts', 1),
                    'created_at': task.get('created_at')
                }
                tasks.append(mapped_task)
            return tasks, None
        else:
            return None, "Unerwartete Antwort beim Abrufen der Aufgaben."
    except Exception as e:
        import traceback
        print(f"Error in get_tasks_for_section: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Aufgaben: {e}"

def get_regular_tasks_for_section(section_id: str) -> tuple[list[dict], str | None]:
    """
    Holt alle regulären Aufgaben eines Abschnitts.
    Nutzt die all_regular_tasks View aus der Task-Type-Trennung.
    """
    if not section_id:
        return [], None
    try:
        session_id = get_session_id()
        if not session_id:
            return [], "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('get_regular_tasks_for_section', {
            'p_session_id': session_id,
            'p_section_id': section_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Abrufen der regulären Aufgaben')
            return [], error_msg
        
        if hasattr(result, 'data'):
            # Map fields if needed
            tasks = []
            for task in (result.data or []):
                mapped_task = {
                    **task,
                    'instruction': task.get('title') or task.get('prompt'),  # Map title/prompt to instruction
                    'assessment_criteria': task.get('grading_criteria', [])
                }
                tasks.append(mapped_task)
            return tasks, None
        return [], f"Fehler beim Abrufen der regulären Aufgaben: Unbekannter Fehler"
    except Exception as e:
        import traceback
        print(f"Error in get_regular_tasks_for_section: {traceback.format_exc()}")
        return [], f"Exception: {str(e)}"

def get_mastery_tasks_for_section(section_id: str) -> tuple[list[dict], str | None]:
    """
    Holt alle Wissensfestiger-Aufgaben eines Abschnitts.
    Nutzt die all_mastery_tasks View aus der Task-Type-Trennung.
    """
    if not section_id:
        return [], None
    try:
        session_id = get_session_id()
        if not session_id:
            return [], "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('get_mastery_tasks_for_section', {
            'p_session_id': session_id,
            'p_section_id': section_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Abrufen der Mastery-Aufgaben')
            return [], error_msg
        
        if hasattr(result, 'data'):
            # Map fields if needed
            tasks = []
            for task in (result.data or []):
                mapped_task = {
                    **task,
                    'instruction': task.get('title') or task.get('prompt'),  # Map title/prompt to instruction
                    'assessment_criteria': [],  # Mastery tasks don't have grading criteria
                    'is_mastery': True
                }
                tasks.append(mapped_task)
            return tasks, None
        return [], f"Fehler beim Abrufen der Mastery-Aufgaben: Unbekannter Fehler"
    except Exception as e:
        import traceback
        print(f"Error in get_mastery_tasks_for_section: {traceback.format_exc()}")
        return [], f"Exception: {str(e)}"

def create_task(section_id: str, instruction: str, task_type: str, assessment_criteria: list[str] | None = None, 
                solution_hints: str | None = None, is_mastery: bool = False, max_attempts: int = 1) -> tuple[dict | None, str | None]:
    """Erstellt eine neue Aufgabe in einem Abschnitt.
    
    Args:
        section_id: ID des Abschnitts
        instruction: Aufgabenstellung
        task_type: Art der Aufgabe (text/file/code)
        assessment_criteria: Liste von Bewertungskriterien (max. 5)
        solution_hints: Lösungshinweise oder Musterlösung
        is_mastery: Ob die Aufgabe eine Wissensfestiger-Aufgabe ist
        max_attempts: Maximale Anzahl erlaubter Einreichungsversuche (Standard: 1)
    
    Returns:
        tuple: (Neue Aufgabe, None) bei Erfolg, (None, Fehlermeldung) bei Fehler.
    """
    if not all([section_id, instruction, task_type]): 
        return None, "Section-ID, Instruction und Task-Type sind erforderlich."
    
    # Validierung der assessment_criteria
    if assessment_criteria and len(assessment_criteria) > 5:
        return None, "Maximal 5 Bewertungskriterien erlaubt."
    
    try:
        # Bestimme die nächste order_in_section
        tasks, error = get_tasks_for_section(section_id)
        if error:
            return None, error
        
        next_order = 0
        if tasks:
            max_order = max(task.get('order_in_section', -1) for task in tasks if task.get('order_in_section') is not None)
            next_order = max_order + 1
        
        insert_data = {
            'section_id': section_id, 
            'instruction': instruction, 
            'task_type': task_type, 
            'order_in_section': next_order,
            'assessment_criteria': assessment_criteria or [],
            'solution_hints': solution_hints,
            'is_mastery': is_mastery,
            'max_attempts': max_attempts
        }
        
        client = get_user_supabase_client()
        
        # Phase 4: Use new structure directly (old columns removed from task table)
        # Views provide backward compatibility, so we only write to new structure
        return create_task_in_new_structure(insert_data)
    except Exception as e:
        error_msg = f"Fehler beim Erstellen der Aufgabe: {e}"
        print(f"Exception in create_task: {e}")
        return None, error_msg

def update_task(task_id: str, instruction: str, assessment_criteria: list[str] | None = None, 
                solution_hints: str | None = None, is_mastery: bool = False, max_attempts: int | None = None) -> tuple[bool, str | None]:
    """Aktualisiert eine Aufgabe.
    
    Args:
        task_id: ID der Aufgabe
        instruction: Neue Aufgabenstellung
        assessment_criteria: Liste von Bewertungskriterien (max. 5)
        solution_hints: Lösungshinweise oder Musterlösung
        is_mastery: Ob die Aufgabe eine Wissensfestiger-Aufgabe ist
        max_attempts: Maximale Anzahl erlaubter Einreichungsversuche (None = nicht ändern)
    
    Returns:
        tuple: (True, None) bei Erfolg, (False, Fehlermeldung) bei Fehler.
    """
    if not task_id:
        return False, "Task-ID ist erforderlich."
    
    # Validierung der assessment_criteria
    if assessment_criteria and len(assessment_criteria) > 5:
        return False, "Maximal 5 Bewertungskriterien erlaubt."
    
    try:
        update_data = {
            'instruction': instruction,
            'assessment_criteria': assessment_criteria or [],
            'solution_hints': solution_hints,
            'is_mastery': is_mastery
        }
        
        # Füge max_attempts nur hinzu wenn explizit gesetzt
        if max_attempts is not None:
            update_data['max_attempts'] = max_attempts
        
        client = get_user_supabase_client()
        
        # Phase 4: Use new structure directly (old columns removed from task table) 
        # Views provide backward compatibility
        updated_task, error = update_task_in_new_structure(task_id, update_data)
        if error:
            error_msg = f"Fehler beim Aktualisieren der Aufgabe: {error}"
            print(f"Fehler in update_task: {error}")
            return False, error_msg
        return True, None
    except Exception as e:
        error_msg = f"Fehler beim Aktualisieren der Aufgabe: {e}"
        print(f"Exception in update_task: {e}")
        return False, error_msg

def delete_task(task_id: str) -> tuple[bool, str | None]:
    """Löscht eine Aufgabe.
    
    Returns:
        tuple: (True, None) bei Erfolg, (False, Fehlermeldung) bei Fehler.
    """
    if not task_id:
        return False, "Task-ID ist erforderlich."
    try:
        client = get_user_supabase_client()
        
        # Phase 4: Use new structure directly (old task table no longer has task data)
        # Views provide backward compatibility 
        success, error = delete_task_in_new_structure(task_id)
        if not success:
            error_msg = f"Fehler beim Löschen der Aufgabe: {error}"
            print(f"Fehler in delete_task: {error}")
            return False, error_msg
        return True, None
    except Exception as e:
        error_msg = f"Fehler beim Löschen der Aufgabe: {e}"
        print(f"Exception in delete_task: {e}")
        return False, error_msg

def move_task_up(task_id: str, section_id: str) -> tuple[bool, str | None]:
    """Verschiebt eine Aufgabe um eine Position nach oben.
    
    Returns:
        tuple: (True, None) bei Erfolg, (False, Fehlermeldung) bei Fehler.
    """
    if not task_id:
        return False, "Task-ID ist erforderlich."
    
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('move_task_up', {
            'p_session_id': session_id,
            'p_task_id': task_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Verschieben der Aufgabe')
            return False, error_msg
        
        return True, None
        
    except Exception as e:
        import traceback
        print(f"Error in move_task_up: {traceback.format_exc()}")
        return False, f"Fehler beim Verschieben der Aufgabe: {e}"

def move_task_down(task_id: str, section_id: str) -> tuple[bool, str | None]:
    """Verschiebt eine Aufgabe um eine Position nach unten.
    
    Returns:
        tuple: (True, None) bei Erfolg, (False, Fehlermeldung) bei Fehler.
    """
    if not task_id:
        return False, "Task-ID ist erforderlich."
    
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('move_task_down', {
            'p_session_id': session_id,
            'p_task_id': task_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Verschieben der Aufgabe')
            return False, error_msg
        
        return True, None
        
    except Exception as e:
        import traceback
        print(f"Error in move_task_down: {traceback.format_exc()}")
        return False, f"Fehler beim Verschieben der Aufgabe: {e}"

# Import from working module to replace broken implementation
from .db.courses import update_course


# Import from working module to replace broken implementation
from .db.courses import delete_course


# Import from working module to replace broken implementation
from .db.core.auth import is_teacher_authorized_for_course


# Import from working module to replace broken implementation
from .db.courses import get_course_by_id
from .db.learning.submissions import (
    update_submission_teacher_override,
    get_remaining_attempts
)

# --- Wissensfestiger (Mastery Learning) Funktionen ---

from datetime import date, datetime, timezone
import random
from typing import Dict, List, Optional, Tuple

# Mastery imports moved to function level to avoid circular dependencies
# This prevents DSPy/OpenAI version conflicts when importing this module


# get_mastery_tasks_for_course is now imported from .db.learning.mastery



# get_next_due_mastery_task is now imported from .db.learning.mastery


# get_next_mastery_task_or_unviewed_feedback is now imported from .db.learning.mastery
# The old implementation has been removed to fix the import conflict.
# The new RPC-based implementation properly handles task prioritization.


def mark_feedback_as_viewed_safe(submission_id: str) -> tuple[bool, str]:
    """
    Markiert Feedback als gelesen mit expliziter Success-Verification.
    Verwendet die neue RPC-Funktion mit Session-basierter Authentifizierung.
    
    Args:
        submission_id: ID der Submission die als gelesen markiert werden soll
        
    Returns:
        Tuple (success: bool, error_message: str)
    """
    import traceback
    
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        if not submission_id:
            return False, "Submission-ID fehlt"
        
        client = get_anon_client()
        result = client.rpc('mark_feedback_as_viewed', {
            'p_session_id': session_id,
            'p_submission_id': submission_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = f"DB Fehler beim Markieren des Feedbacks: {result.error.get('message', 'Unbekannter Fehler')}"
            print(f"❌ {error_msg}")
            return False, error_msg
        
        # Check if update was successful (result.data should be True if row was updated)
        success = bool(result.data) if result.data is not None else False
        
        if success:
            print(f"✅ Feedback für Submission {submission_id} als gelesen markiert")
            return True, ""
        else:
            print(f"⚠️ Feedback für Submission {submission_id} konnte nicht markiert werden (evtl. bereits gelesen)")
            return False, "Feedback konnte nicht markiert werden"
        
    except Exception as e:
        error_msg = f"Exception beim Markieren des Feedbacks: {str(e)}"
        print(f"❌ {error_msg}\n{traceback.format_exc()}")
        return False, error_msg


def save_mastery_submission(student_id: str, task_id: str, answer: str, assessment: dict) -> tuple[dict | None, str | None]:
    """
    Speichert die Antwort und die KI-Bewertung eines Schülers in der mastery_submission Tabelle.
    """
    try:
        q_vec = assessment.get('q_vec', {})
        insert_data = {
            'student_id': student_id,
            'task_id': task_id,
            'answer_text': answer,
            'korrektheit': q_vec.get('korrektheit'),
            'vollstaendigkeit': q_vec.get('vollstaendigkeit'),
            'praegnanz': q_vec.get('praegnanz'),
            'reasoning': assessment.get('reasoning')
        }
        
        client = get_user_supabase_client()
        response = client.table('mastery_submission').insert(insert_data).execute()

        if hasattr(response, 'error') and response.error:
            return None, f"Fehler beim Speichern der Antwort: {response.error.message}"
            
        return response.data[0] if response.data else None, None

    except Exception as e:
        return None, f"Unerwarteter Fehler beim Speichern der Antwort: {e}"


# ENTFERNT: Alte update_mastery_progress Funktion - verwende stattdessen _update_mastery_progress


def submit_mastery_answer(student_id: str, task_id: str, answer: str) -> tuple[dict | None, str | None]:
    """
    Verarbeitet eine Wissensfestiger-Antwort: KI-Bewertung & Feedback, Speicherung, Fortschritts-Update.
    """
    from ai.feedback import CombinedMasteryFeedbackModule
    try:
        # 1. Hole Aufgabendetails für die KI
        task_details, error = get_task_details(task_id)
        if error or not task_details:
            return None, error or f"Aufgabe nicht gefunden: {task_id}"

        # 2. Lade Submission-Historie (letzter Versuch)
        submission_history_str = "Dies ist der erste Versuch für diese Aufgabe."
        history, error = get_submission_history(student_id, task_id)
        if error:
            print(f"WARNUNG: Konnte Submission-Historie nicht laden: {error}")
        elif history:
            last_submission = history[-1]
            solution_text = last_submission.get("submission_data", {}).get("text", "(Kein Text)")
            submission_history_str = f"---\n{solution_text}\n---"

        # 3. Generiere kombinierte KI-Bewertung und pädagogisches Feedback
        ai_module = CombinedMasteryFeedbackModule()
        ai_result = ai_module(
            task_details=task_details,
            student_answer=answer,
            submission_history=submission_history_str
        )
        
        q_vec = ai_result.get("q_vec")
        if not q_vec:
            return None, "Fehler bei der KI-Bewertung, kein q_vec erhalten."

        # 4. Speichere die Einreichung mit allen KI-Ergebnissen via Service Client
        service_client = get_supabase_service_client()
        if not service_client:
            return None, "Service Client nicht verfügbar."

        # 4a. Zähle vorhandene Einreichungen für diese Aufgabe
        count_response = (
            service_client
            .table("submission")
            .select("id")
            .eq("student_id", student_id)
            .eq("task_id", task_id)
            .execute()
        )
        
        if hasattr(count_response, "error") and count_response.error:
            return None, f"Fehler beim Zählen der Einreichungen: {count_response.error.message}"
        
        current_attempts = len(count_response.data) if count_response.data else 0
        attempt_number = current_attempts + 1

        submission_data = {
            "student_id": student_id,
            "task_id": task_id,
            "submission_data": {"text": answer},
            "ai_criteria_analysis": q_vec,
            "feed_back_text": ai_result.get("feed_back_text"),
            "feed_forward_text": ai_result.get("feed_forward_text"),
            "ai_feedback": f"{ai_result.get('feed_back_text')}\n\n{ai_result.get('feed_forward_text')}",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "attempt_number": attempt_number
        }
        
        insert_response = (
            service_client
            .table("submission")
            .insert(submission_data)
            .execute()
        )
        if hasattr(insert_response, "error") and insert_response.error:
            print(f"WARNUNG: Konnte Wissensfestiger-Antwort nicht speichern: {insert_response.error}")

        # 5. Aktualisiere den Lernfortschritt (ebenfalls mit Service Client)
        success, error = _update_mastery_progress(student_id, task_id, q_vec, service_client)
        if not success:
            print(f"FEHLER: Konnte Lernfortschritt nicht aktualisieren: {error}")
        
        # 6. Gib das vollständige KI-Ergebnis an die UI zurück
        return ai_result, None

    except Exception as e:
        print(f"Traceback in submit_mastery_answer: {traceback.format_exc()}")
        return None, f"Fehler bei der Verarbeitung der Antwort: {e}"



def get_mastery_stats_for_student(student_id: str, course_id: str) -> tuple[dict | None, str | None]:
    """
    Holt Statistiken zum Wissensfestiger-Fortschritt eines Schülers für einen Kurs.
    """
    try:
        mastery_tasks, error = get_mastery_tasks_for_course(course_id)
        if error:
            return None, error
        
        if not mastery_tasks:
            return {
                "total_tasks": 0,
                "mastered": 0,
                "learning": 0,
                "not_started": 0,
                "avg_stability": 0
            }, None

        task_ids = [task["id"] for task in mastery_tasks]
        
        client = get_user_supabase_client()
        progress_response = (
            client
            .table("student_mastery_progress")
            .select("stability, difficulty, task_id, last_reviewed_at, next_due_date")
            .eq("student_id", student_id)
            .in_("task_id", task_ids)
            .execute()
        )
            
        if hasattr(progress_response, "error") and progress_response.error:
            return None, f"Fehler beim Abrufen des Fortschritts: {progress_response.error.message}"
        
        progress_data = progress_response.data if hasattr(progress_response, "data") else []
        
        stats = {
            "total_tasks": len(mastery_tasks),
            "mastered": 0,
            "learning": 0,
            "not_started": 0,
            "avg_stability": 0
        }
        
        total_stability = 0
        tasks_with_progress = 0
        
        progress_by_task = {p["task_id"]: p for p in progress_data} if progress_data else {}

        for task_id in task_ids:
            progress = progress_by_task.get(task_id)
            if not progress:
                stats["not_started"] += 1
            else:
                # Ohne state-Feld: Nutze stability als Indikator
                stability = progress.get("stability", 0)
                if stability > 21:  # Hohe Stabilität = gemeistert
                    stats["mastered"] += 1
                elif stability > 0:  # Niedrige Stabilität = am lernen
                    stats["learning"] += 1
                else:
                    stats["not_started"] += 1
                
                if stability > 0:
                    total_stability += stability
                    tasks_with_progress += 1
        
        if tasks_with_progress > 0:
            stats["avg_stability"] = total_stability / tasks_with_progress
            
        return stats, None

    except Exception as e:
        print(f"Exception in get_mastery_stats_for_student: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Statistiken: {e}"


# --- Interne Hilfsfunktionen für Mastery --- 

def _update_mastery_progress(student_id: str, task_id: str, q_vec: dict, service_client) -> tuple[bool, str | None]:
    """
    Interne Funktion zum Aktualisieren des Lernfortschritts.
    Wird vom Worker aufgerufen und nutzt die service-role RPC-Funktion.
    """
    if not service_client:
        return False, "Service Client nicht verfügbar."

    try:
        # Nutze die neue service-role RPC-Funktion
        result = service_client.rpc('update_mastery_progress_service', {
            'p_student_id': student_id,
            'p_task_id': task_id,
            'p_q_vec': json.dumps(q_vec)
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Update des Fortschritts')
            return False, error_msg
            
        if result.data:
            response_data = result.data
            if response_data.get('success'):
                return True, None
            else:
                return False, response_data.get('error', 'Unbekannter Fehler')
        
        return False, "Keine Antwort von der Datenbank"

    except Exception as e:
        print(f"Exception in _update_mastery_progress: {traceback.format_exc()}")
        return False, f"Fehler bei der Fortschrittsberechnung: {e}"



# --- Feedback-Funktionen ---

# Functions moved to db/platform/feedback.py
# Import at top of file provides these functions

# --- Weitere DB-Funktionen können hier hinzugefügt werden ---


# REMOVED: Duplicate get_next_due_mastery_task - using RPC version above
# def get_next_due_mastery_task(student_id: str, course_id: int) -> tuple[dict | None, str | None]:
#     """
#     Holt die nächste fällige Mastery-Aufgabe für einen Schüler in einem Kurs.
#     Implementiert Interleaving durch Mischen aller fälligen Aufgaben.
#     
#     Args:
#         student_id: ID des Schülers
#         course_id: ID des Kurses
#         
#     Returns:
#         tuple: (Aufgaben-Dict mit zusätzlichen Progress-Infos, None) bei Erfolg, 
#                (None, Fehlermeldung) bei Fehler oder keine fällige Aufgabe.
#     """
#     try:
#         from datetime import date
#         import random
#         
#         # 1. Hole alle Mastery-Aufgaben des Kurses
#         mastery_tasks, error = get_mastery_tasks_for_course(course_id)
#         if error or not mastery_tasks:
#             return None, error or "Keine Mastery-Aufgaben in diesem Kurs"
#         
#         # 2. Hole Progress-Daten für diesen Schüler
#         client = get_user_supabase_client()
#         progress_response = client.table('student_mastery_progress') \
#             .select('*') \
#             .eq('student_id', student_id) \
#             .execute()
#         
#         progress_by_task = {}
#         if hasattr(progress_response, 'data') and progress_response.data:
#             for p in progress_response.data:
#                 progress_by_task[p['task_id']] = p
#         
#         # 3. Finde fällige Aufgaben
#         today = date.today()
#         due_tasks = []
#         
#         for task in mastery_tasks:
#             task_id = task['id']
#             
#             # Wenn noch kein Progress existiert, ist die Aufgabe sofort fällig
#             if task_id not in progress_by_task:
#                 due_tasks.append(task)
#             else:
#                 progress = progress_by_task[task_id]
#                 due_date = progress.get('next_due_date')
#                 
#                 # Prüfe ob fällig
#                 if due_date:
#                     if isinstance(due_date, str):
#                         due_date = date.fromisoformat(due_date)
#                     if due_date <= today:
#                         # Füge Progress-Info zur Aufgabe hinzu
#                         task['mastery_progress'] = progress
#                         due_tasks.append(task)
#         
#         if not due_tasks:
#             return None, "Keine Aufgaben fällig heute. Komm morgen wieder!"
#         
#         # 4. Interleaving: Wähle zufällig eine der fälligen Aufgaben
#         # (In Zukunft könnte hier eine sophistiziertere Logik stehen)
#         selected_task = random.choice(due_tasks)
#         
#         return selected_task, None
#         
#     except Exception as e:
#         return None, f"Fehler beim Abrufen der nächsten Aufgabe: {e}"


def get_mastery_overview_for_teacher(course_id: int) -> tuple[list | None, str | None]:
    """
    Holt eine Übersicht aller Schüler und deren Mastery-Fortschritt für einen Kurs.
    
    Args:
        course_id: ID des Kurses
        
    Returns:
        tuple: (Liste mit Schüler-Fortschritt-Daten, None) bei Erfolg,
               (None, Fehlermeldung) bei Fehler.
    """
    try:
        # 1. Hole alle Schüler des Kurses
        client = get_user_supabase_client()
        students_response = client.table('course_student') \
            .select('student_id, profiles!inner(full_name, email)') \
            .eq('course_id', course_id) \
            .execute()
        
        if not hasattr(students_response, 'data'):
            return [], None
            
        students = students_response.data
        
        # 2. Hole alle Mastery-Tasks
        tasks, error = get_mastery_tasks_for_course(course_id)
        if error or not tasks:
            return [], None
            
        task_ids = [t['id'] for t in tasks]
        
        # 3. Hole Progress für alle Schüler
        client = get_user_supabase_client()
        progress_response = client.table('student_mastery_progress') \
            .select('*') \
            .in_('task_id', task_ids) \
            .execute()
        
        progress_by_student = {}
        if hasattr(progress_response, 'data'):
            for p in progress_response.data:
                student_id = p['student_id']
                if student_id not in progress_by_student:
                    progress_by_student[student_id] = []
                progress_by_student[student_id].append(p)
        
        # 4. Erstelle Übersicht
        overview = []
        for student in students:
            student_id = student['student_id']
            student_progress = progress_by_student.get(student_id, [])
            
            # Berechne Stats für diesen Schüler
            mastered = sum(1 for p in student_progress 
                          if p.get('status') == 'reviewing' and p.get('current_interval', 0) > 21)
            learning = sum(1 for p in student_progress if p.get('status') == 'learning')
            
            overview.append({
                'student_id': student_id,
                'student_name': student['profiles']['full_name'],
                'student_email': student['profiles']['email'],
                'total_tasks': len(tasks),
                'started_tasks': len(student_progress),
                'mastered_tasks': mastered,
                'learning_tasks': learning,
                'completion_rate': (mastered / len(tasks) * 100) if tasks else 0
            })
        
        # Sortiere nach Completion Rate
        overview.sort(key=lambda x: x['completion_rate'], reverse=True)
        
        return overview, None
        
    except Exception as e:
        return None, f"Fehler beim Abrufen der Lehrer-Übersicht: {e}"

# --- Optimierte Mastery Progress Funktionen ---

# get_mastery_progress_summary is imported from .db.learning.mastery

# calculate_learning_streak is imported from .db.learning.progress

# --- Feedback-Funktionen ---


