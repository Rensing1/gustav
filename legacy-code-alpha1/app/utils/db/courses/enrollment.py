"""Course enrollment functions for HttpOnly Cookie support.

This module contains all enrollment-related database functions that have been
migrated to use the RPC pattern with session-based authentication.
"""

import streamlit as st
from typing import Optional, Dict, Any, List, Tuple
import traceback

from ..core.session import get_session_id, get_anon_client, handle_rpc_result


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
        
        # RPC should return a list of course IDs
        if hasattr(result, 'data') and result.data:
            return [str(course_id) for course_id in result.data]
        
        return []
    except Exception as e:
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
        # Just ensure sorting by name
        courses = sorted(data, key=lambda x: (x.get('name') or ''))
        
        return courses, None
    except Exception as e:
        print(f"Error in get_student_courses: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Kurse: {str(e)}"


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
        
        # Ensure all students have expected fields
        students = []
        for student in data:
            students.append({
                'student_id': student.get('student_id'),
                'full_name': student.get('full_name') or student.get('display_name', ''),
                'email': student.get('email', '')
            })
        
        return students, None
    except Exception as e:
        print(f"Error in get_course_students: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Kursteilnehmer: {str(e)}"


def get_published_section_details_for_student(unit_id: str, course_id: str, student_id: str) -> tuple[list | None, str | None]:
    """Holt die Details aller veröffentlichten Abschnitte einer Lerneinheit
       für einen bestimmten Schüler in einem Kurs.

    Args:
        unit_id: ID der Lerneinheit (wird von der UI übergeben, aber nicht von der SQL-Funktion benötigt)
        course_id: ID des Kurses
        student_id: ID des Schülers (wird von der UI übergeben, aber nicht von der SQL-Funktion benötigt)

    Returns:
        tuple: (Liste der Abschnitte, None) bei Erfolg, (None, Fehlermeldung) bei Fehler.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        if not course_id:
            return [], None
        
        # Verwende die neue 4-Parameter Version der SQL-Funktion
        client = get_anon_client()
        result = client.rpc('get_published_section_details_for_student', {
            'p_session_id': session_id,
            'p_course_id': course_id,
            'p_unit_id': unit_id,
            'p_student_id': student_id
        }).execute()
        
        data, error = handle_rpc_result(result, [])
        if error:
            return None, error
        
        # Return sections sorted by order_in_unit (section_order in der SQL-Response)
        sections = sorted(data, key=lambda x: x.get('section_order', x.get('order_in_unit', 0)))
        
        # Map SQL response fields to expected format
        formatted_sections = []
        for section in sections:
            # Get all tasks from SQL response
            all_tasks = section.get('tasks', [])
            
            # Filter out mastery tasks (which have order_in_section = 999)
            regular_tasks = [
                task for task in all_tasks 
                if task.get('order_in_section', 0) != 999
            ]
            
            formatted_section = {
                'id': section.get('section_id'),
                'title': section.get('section_title'),
                'order_in_unit': section.get('order_in_unit', 0),
                'materials': section.get('section_materials', []),
                'tasks': regular_tasks  # Only regular tasks (order_in_section != 999)
            }
            formatted_sections.append(formatted_section)
        
        return formatted_sections, None
        
    except Exception as e:
        print(f"Error in get_published_section_details_for_student: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Abschnitte: {str(e)}"