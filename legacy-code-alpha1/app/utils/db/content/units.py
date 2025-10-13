"""Learning unit management functions for HttpOnly Cookie support.

This module contains all learning unit-related database functions that have been
migrated to use the RPC pattern with session-based authentication.
"""

import streamlit as st
from typing import Optional, Dict, Any, List, Tuple
import traceback

from ..core.session import get_session_id, get_anon_client, handle_rpc_result


def get_learning_units_by_creator(creator_id: str = None) -> tuple[list | None, str | None]:
    """Holt alle Lerneinheiten des aktuellen Users über PostgreSQL Function (HttpOnly Cookie Support)"""
    try:
        session_id = get_session_id()
        if not session_id:
            return [], "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('get_user_learning_units', {
            'p_session_id': session_id
        }).execute()
        
        return handle_rpc_result(result, [])
    
    except Exception as e:
        print(f"Error in get_learning_units_by_creator: {traceback.format_exc()}")
        return [], f"Fehler beim Laden der Lerneinheiten: {str(e)}"


def create_learning_unit(title: str, creator_id: str = None) -> tuple[dict | None, str | None]:
    """Erstellt eine neue Lerneinheit über PostgreSQL Function (HttpOnly Cookie Support)"""
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        if not title:
            return None, "Titel ist erforderlich."
        
        client = get_anon_client()
        result = client.rpc('create_learning_unit', {
            'p_session_id': session_id,
            'p_title': title,
            'p_description': None  # Optional description parameter
        }).execute()
        
        data, error = handle_rpc_result(result, [])
        if error:
            return None, error
        
        # PostgreSQL Function gibt ein Array zurück, wir wollen das erste Element
        if data and len(data) > 0:
            unit_data = data[0]
            if unit_data.get('success'):
                return {
                    'id': unit_data.get('id'),
                    'title': unit_data.get('title'),
                    'created_at': unit_data.get('created_at')
                }, None
            else:
                return None, unit_data.get('error_message', 'Unbekannter Fehler')
        
        return None, "Keine Daten von der Datenbank erhalten"
    
    except Exception as e:
        print(f"Error in create_learning_unit: {traceback.format_exc()}")
        return None, f"Fehler beim Erstellen der Lerneinheit: {str(e)}"


def update_learning_unit(unit_id: str, title: str) -> tuple[bool, str | None]:
    """Aktualisiert den Titel einer Lerneinheit.
    
    Returns:
        tuple: (True, None) bei Erfolg, (False, Fehlermeldung) bei Fehler.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        if not all([unit_id, title]):
            return False, "Unit-ID und Titel sind erforderlich."
        
        client = get_anon_client()
        result = client.rpc('update_learning_unit', {
            'p_session_id': session_id,
            'p_unit_id': unit_id,
            'p_title': title
        }).execute()
        
        # RPC returns void on success, raises exception on error
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Aktualisieren der Lerneinheit')
            return False, error_msg
        
        return True, None
    except Exception as e:
        print(f"Error in update_learning_unit: {traceback.format_exc()}")
        return False, f"Fehler beim Aktualisieren der Lerneinheit: {str(e)}"


def delete_learning_unit(unit_id: str) -> tuple[bool, str | None]:
    """Löscht eine Lerneinheit.
    
    Returns:
        tuple: (True, None) bei Erfolg, (False, Fehlermeldung) bei Fehler.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        if not unit_id:
            return False, "Unit-ID ist erforderlich."
        
        client = get_anon_client()
        result = client.rpc('delete_learning_unit', {
            'p_session_id': session_id,
            'p_unit_id': unit_id
        }).execute()
        
        # RPC returns void on success, raises exception on error
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Löschen der Lerneinheit')
            return False, error_msg
        
        return True, None
    except Exception as e:
        print(f"Error in delete_learning_unit: {traceback.format_exc()}")
        return False, f"Fehler beim Löschen der Lerneinheit: {str(e)}"


def get_learning_unit_by_id(unit_id: str) -> tuple[dict | None, str | None]:
    """Holt eine einzelne Lerneinheit über PostgreSQL Function.
    
    Returns:
        tuple: (Lerneinheit, None) bei Erfolg, (None, Fehlermeldung) bei Fehler.
    """
    if not unit_id:
        return None, "Unit-ID ist erforderlich."
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"

        client = get_anon_client()
        result = client.rpc('get_learning_unit', {
            'p_session_id': session_id,
            'p_unit_id': unit_id
        }).execute()

        data, error = handle_rpc_result(result, [])
        if error:
            return None, error
        
        if data and len(data) > 0:
            return data[0], None
        else:
            return None, "Lerneinheit nicht gefunden."
    except Exception as e:
        error_msg = f"Fehler beim Abrufen der Lerneinheit: {e}"
        print(f"Exception in get_learning_unit_by_id: {e}")
        return None, error_msg