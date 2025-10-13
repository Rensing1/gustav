"""Section management functions for HttpOnly Cookie support.

This module contains all section-related database functions that have been
migrated to use the RPC pattern with session-based authentication.
"""

import json
import traceback
from typing import Optional, Dict, Any, List, Tuple

from ..core.session import get_session_id, get_anon_client, handle_rpc_result


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
        print(f"Error in create_section: {traceback.format_exc()}")
        return None, f"Fehler: {str(e)}"


def get_sections_for_unit(unit_id: str) -> tuple[list | None, str | None]:
    """Holt alle Abschnitte über PostgreSQL Function.

    Returns:
        tuple: (Liste der Abschnitte, None) bei Erfolg, (None, Fehlermeldung) bei Fehler.
    """
    if not unit_id: return [], None
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"

        client = get_anon_client()
        result = client.rpc('get_unit_sections', {
            'p_session_id': session_id,
            'p_unit_id': unit_id
        }).execute()

        data, error = handle_rpc_result(result, [])
        if error:
            return None, error
        
        return data or [], None

    except Exception as e:
        error_msg = f"Unerwarteter Python-Fehler beim Abrufen der Abschnitte für Einheit {unit_id}: {e}"
        print(f"Exception in get_sections_for_unit: {e}")
        return None, error_msg


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
        print(f"Error in update_section_materials: {traceback.format_exc()}")
        return False, f"Fehler: {str(e)}"