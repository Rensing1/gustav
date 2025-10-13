"""Course management functions for HttpOnly Cookie support.

This module contains all course-related database functions that have been
migrated to use the RPC pattern with session-based authentication.
"""

import streamlit as st
from typing import Optional, Dict, Any, List, Tuple
import uuid
from datetime import datetime
import traceback

from ..core.session import get_session_id, get_anon_client, handle_rpc_result


def get_courses_by_creator(creator_id: str = None) -> tuple[list | None, str | None]:
    """Lädt Kurse des aktuellen Users über PostgreSQL Function (HttpOnly Cookie Support)"""
    try:
        session_id = get_session_id()
        if not session_id:
            return [], "Keine aktive Session gefunden"

        client = get_anon_client()
        result = client.rpc('get_user_courses', {
            'p_session_id': session_id
        }).execute()

        return handle_rpc_result(result, [])
    
    except Exception as e:
        print(f"Error in get_courses_by_creator: {traceback.format_exc()}")
        return [], f"Fehler beim Laden der Kurse: {str(e)}"


def create_course(name: str, creator_id: str = None) -> tuple[dict | None, str | None]:
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


def get_students_in_course(course_id: str) -> tuple[list | None, str | None]:
    """Holt alle Schüler (id, email, full_name), die in einem bestimmten Kurs eingeschrieben sind.

    Returns:
        tuple: (Liste der Schüler-Profile, None) bei Erfolg, (None, Fehlermeldung) bei Fehler.
    """
    if not course_id: return [], None
    try:
        session_id = get_session_id()
        if not session_id:
            return [], "Keine aktive Session gefunden"

        client = get_anon_client()
        result = client.rpc('get_students_in_course', {
            'p_session_id': session_id,
            'p_course_id': course_id
        }).execute()

        # Map display_name to full_name for backwards compatibility
        if hasattr(result, 'data') and result.data:
            for student in result.data:
                display_name = student.pop('display_name', '')
                # Use email prefix as fallback (same logic as before)
                if not display_name or display_name == 'None':
                    email = student.get('email', '')
                    student['full_name'] = email.split('@')[0] if '@' in email else email
                else:
                    student['full_name'] = display_name
                # Remove course_id as it's not in the old response format
                student.pop('course_id', None)
        
        return handle_rpc_result(result, [])
    except Exception as e:
        print(f"Error in get_students_in_course: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Schüler: {str(e)}"


def get_teachers_in_course(course_id: str) -> tuple[list | None, str | None]:
    """Holt alle Lehrer (id, email, full_name), die einem bestimmten Kurs zugewiesen sind.

    Returns:
        tuple: (Liste der Lehrer-Profile, None) bei Erfolg, (None, Fehlermeldung) bei Fehler.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return [], "Keine aktive Session gefunden"
        
        if not course_id:
            return [], None
        
        client = get_anon_client()
        result = client.rpc('get_teachers_in_course', {
            'p_session_id': session_id,
            'p_course_id': course_id
        }).execute()
        
        data, error = handle_rpc_result(result, [])
        if error:
            return None, error
        
        # Map display_name to full_name for compatibility
        teachers = []
        for teacher in data:
            teachers.append({
                'id': teacher.get('teacher_id'),
                'email': teacher.get('email'),
                'full_name': teacher.get('display_name') or teacher.get('email', '').split('@')[0]
            })
        
        return teachers, None
    except Exception as e:
        print(f"Error in get_teachers_in_course: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Lehrer: {str(e)}"


def add_user_to_course(course_id: str, user_id: str, role: str) -> tuple[bool, str | None]:
    """Fügt einen Schüler oder Lehrer zu einem Kurs hinzu.

    Returns:
        tuple: (True, None) bei Erfolg oder wenn bereits vorhanden, (False, Fehlermeldung) bei Fehler.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        if not course_id or not user_id or not role:
            return False, "Kurs-ID, Benutzer-ID und Rolle sind erforderlich."
        
        if role not in ['student', 'teacher']:
            return False, "Rolle muss 'student' oder 'teacher' sein."
        
        client = get_anon_client()
        result = client.rpc('add_user_to_course', {
            'p_session_id': session_id,
            'p_user_id': user_id,
            'p_course_id': course_id,
            'p_role': role
        }).execute()
        
        # RPC returns void on success, raises exception on error
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Hinzufügen des Benutzers')
            return False, error_msg
        
        return True, None
    except Exception as e:
        print(f"Error in add_user_to_course: {traceback.format_exc()}")
        return False, f"Fehler beim Hinzufügen des Benutzers: {str(e)}"


def remove_user_from_course(course_id: str, user_id: str, role: str) -> tuple[bool, str | None]:
    """Entfernt einen Schüler oder Lehrer aus einem Kurs.

    Returns:
        tuple: (True, None) bei Erfolg, (False, Fehlermeldung) bei Fehler.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        if not course_id or not user_id or not role:
            return False, "Kurs-ID, Benutzer-ID und Rolle sind erforderlich."
        
        if role not in ['student', 'teacher']:
            return False, "Rolle muss 'student' oder 'teacher' sein."
        
        client = get_anon_client()
        result = client.rpc('remove_user_from_course', {
            'p_session_id': session_id,
            'p_user_id': user_id,
            'p_course_id': course_id,
            'p_role': role
        }).execute()
        
        # RPC returns void on success, raises exception on error
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Entfernen des Benutzers')
            return False, error_msg
        
        return True, None
    except Exception as e:
        print(f"Error in remove_user_from_course: {traceback.format_exc()}")
        return False, f"Fehler beim Entfernen des Benutzers: {str(e)}"


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
        
        # DEBUG: Print the actual data structure
        print(f"DEBUG get_courses_assigned_to_unit raw data: {data}")
        
        # Map id and name from RPC result to expected format
        courses = []
        for course in data:
            courses.append({
                'id': course.get('id'),
                'name': course.get('name')
            })
        
        return courses, None
    except Exception as e:
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
        print(f"Error in unassign_unit_from_course: {traceback.format_exc()}")
        return False, f"Fehler beim Entfernen der Zuweisung: {str(e)}"


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
        print(f"Error in get_section_statuses_for_unit_in_course: {traceback.format_exc()}")
        return None, f"Fehler: {str(e)}"


def update_course(course_id: str, name: str) -> tuple[bool, str | None]:
    """Aktualisiert den Namen eines Kurses.
    
    Returns:
        tuple: (True, None) bei Erfolg, (False, Fehlermeldung) bei Fehler.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        if not course_id or not name or not name.strip():
            return False, "Kurs-ID und Name sind erforderlich."
        
        client = get_anon_client()
        result = client.rpc('update_course', {
            'p_session_id': session_id,
            'p_course_id': course_id,
            'p_name': name.strip()
        }).execute()
        
        # RPC returns void on success, raises exception on error
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Aktualisieren des Kurses')
            return False, error_msg
        
        return True, None
    except Exception as e:
        print(f"Error in update_course: {traceback.format_exc()}")
        return False, f"Fehler beim Aktualisieren des Kurses: {str(e)}"


def delete_course(course_id: str) -> tuple[bool, str | None]:
    """Löscht einen Kurs. Durch CASCADE werden auch alle Zuweisungen gelöscht.
    
    Returns:
        tuple: (True, None) bei Erfolg, (False, Fehlermeldung) bei Fehler.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        if not course_id:
            return False, "Kurs-ID ist erforderlich."
        
        client = get_anon_client()
        result = client.rpc('delete_course', {
            'p_session_id': session_id,
            'p_course_id': course_id
        }).execute()
        
        # RPC returns void on success, raises exception on error
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Löschen des Kurses')
            return False, error_msg
        
        return True, None
    except Exception as e:
        print(f"Error in delete_course: {traceback.format_exc()}")
        return False, f"Fehler beim Löschen des Kurses: {str(e)}"


def get_course_by_id(course_id: str) -> tuple[dict | None, str | None]:
    """Holt einen einzelnen Kurs.
    
    Returns:
        tuple: (Kurs, None) bei Erfolg, (None, Fehlermeldung) bei Fehler.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        if not course_id:
            return None, "Course-ID ist erforderlich."
        
        client = get_anon_client()
        result = client.rpc('get_course_by_id', {
            'p_session_id': session_id,
            'p_course_id': course_id
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
            return None, "Kurs nicht gefunden."
        
    except Exception as e:
        print(f"Error in get_course_by_id: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen des Kurses: {str(e)}"