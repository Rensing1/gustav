"""Platform feedback functions for HttpOnly Cookie support.

This module contains all platform feedback-related functions
that have been migrated to use the RPC pattern with session-based 
authentication.
"""

import streamlit as st
import json
import traceback
from ..core.session import get_session_id, get_anon_client, handle_rpc_result


def submit_feedback(feedback_type: str, message: str) -> bool:
    """Speichert anonymes Schüler-Feedback.
    
    Args:
        feedback_type: 'unterricht' oder 'plattform'
        message: Feedback-Nachricht
        
    Returns:
        bool: True bei Erfolg, False bei Fehler
    """
    try:
        session_id = get_session_id()
        # Allow anonymous feedback (no session required)
        
        # Hole den aktuellen Page Context
        page_identifier = 'unknown'
        if hasattr(st.session_state, 'current_page'):
            page_identifier = st.session_state.current_page
        elif hasattr(st, 'query_params'):
            page_identifier = st.query_params.get('page', 'unknown')
        
        # Prepare metadata
        metadata = {
            'source': 'feedback_popup',
            'feedback_category': feedback_type
        }
        
        client_anon = get_anon_client()
        result = client_anon.rpc('submit_feedback', {
            'p_session_id': session_id,
            'p_page_identifier': page_identifier,
            'p_feedback_type': feedback_type,
            'p_feedback_text': message,  # Map message to feedback_text
            'p_sentiment': None,
            'p_metadata': json.dumps(metadata)
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            print(f"Fehler beim Speichern des Feedbacks: {result.error}")
            return False
            
        return True
        
    except Exception as e:
        print(f"Fehler beim Speichern des Feedbacks: {e}")
        return False


def get_all_feedback() -> list:
    """Holt alle Feedback-Einträge für Lehrer.
    
    Returns:
        list: Liste aller Feedback-Einträge, sortiert nach Datum (neueste zuerst)
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return []
        
        # Use anon client for RPC call
        anon_client = get_anon_client()
        result = anon_client.rpc('get_all_feedback', {
            'p_session_id': session_id
        }).execute()
        
        data, error = handle_rpc_result(result, [])
        if error:
            print(f"Error in get_all_feedback: {error}")
            return []
        
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Error in get_all_feedback: {traceback.format_exc()}")
        return []