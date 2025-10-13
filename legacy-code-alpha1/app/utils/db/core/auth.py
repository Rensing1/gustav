"""Authentication and authorization functions for HttpOnly Cookie support.

This module contains functions related to user authentication, authorization,
and role management that have been migrated to use the RPC pattern with
session-based authentication.
"""

import streamlit as st
from typing import Optional, Dict, Any, List, Tuple
import traceback

from .session import get_session_id, get_anon_client, handle_rpc_result


def get_users_by_role(role: str) -> tuple[list | None, str | None]:
    """Holt alle Benutzer (id, email, display_name) mit einer bestimmten Rolle über PostgreSQL Function.
    Returns:
        tuple: (Liste der Nutzer, None) bei Erfolg, (None, Fehlermeldung) bei Fehler.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return [], "Keine aktive Session gefunden"
        client = get_anon_client()
        result = client.rpc('get_users_by_role', {
            'p_session_id': session_id,
            'p_role': role
        }).execute()
        # Map display_name to full_name for backwards compatibility
        if hasattr(result, 'data') and result.data:
            for user in result.data:
                user['full_name'] = user.pop('display_name', '')
        
        return handle_rpc_result(result, [])
    except Exception as e:
        import traceback
        print(f"Error in get_users_by_role: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Benutzer: {str(e)}"


def is_teacher_authorized_for_course(teacher_id: str, course_id: str) -> tuple[bool, str | None]:
    """Prüft, ob ein Lehrer berechtigt ist, einen Kurs zu verwalten.
    Ein Lehrer ist berechtigt wenn er:
    1. Der Ersteller (creator_id) des Kurses ist ODER
    2. In der course_teacher Tabelle für diesen Kurs eingetragen ist
    
    Returns:
        tuple: (True, None) wenn berechtigt, (False, Grund) wenn nicht berechtigt
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        if not teacher_id or not course_id:
            return False, "Lehrer-ID und Kurs-ID sind erforderlich."
        
        # Note: This function uses the session's user, not the passed teacher_id
        # The RPC function checks if the session user is authorized for the course
        client = get_anon_client()
        result = client.rpc('is_teacher_authorized_for_course', {
            'p_session_id': session_id,
            'p_course_id': course_id
        }).execute()
        
        # RPC returns boolean
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler bei der Berechtigungsprüfung')
            return False, error_msg
        
        if result.data is True:
            return True, None
        else:
            return False, "Sie sind nicht berechtigt, diesen Kurs zu verwalten."
    except Exception as e:
        import traceback
        print(f"Error in is_teacher_authorized_for_course: {traceback.format_exc()}")
        return False, f"Fehler bei der Berechtigungsprüfung: {str(e)}"