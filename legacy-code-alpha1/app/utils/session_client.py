# app/utils/session_client.py
"""
Session-isolierter Supabase Client.

Jeder User bekommt seinen eigenen Client mit eigener Session,
um Session-Vermischungen bei mehreren gleichzeitigen Nutzern zu verhindern.
"""

import streamlit as st
from supabase import create_client, Client, ClientOptions
from config import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY
import time
from typing import Optional
import threading


def get_user_supabase_client() -> Client:
    """
    Gibt einen Supabase Client zurück, der an die aktuelle User-Session gebunden ist.
    
    Jeder User hat seinen eigenen Client im session_state, um Vermischungen zu verhindern.
    Der Client wird mit dem User-Token initialisiert, falls vorhanden.
    
    Returns:
        Client: Supabase Client für den aktuellen User
    """
    # Prüfe ob Client bereits im session_state existiert
    if 'user_supabase_client' not in st.session_state:
        # Erstelle neuen Client
        options = ClientOptions(
            postgrest_client_timeout=120,
            storage_client_timeout=120
        )
        client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY, options=options)
        
        # Wenn User eingeloggt ist, setze die Session
        if 'session' in st.session_state and st.session_state.session:
            try:
                # Handle both dict and object session formats
                if isinstance(st.session_state.session, dict):
                    # HttpOnly mode: session is a dict
                    access_token = st.session_state.session.get('access_token')
                    refresh_token = st.session_state.session.get('refresh_token')
                else:
                    # Legacy mode: session is an object with attributes
                    access_token = st.session_state.session.access_token
                    refresh_token = st.session_state.session.refresh_token
                
                # Skip Supabase session setup in HttpOnly mode
                if access_token == 'managed-by-cookies':
                    # In HttpOnly mode, we don't have real tokens
                    # Authentication is handled by nginx/cookies
                    pass
                else:
                    # Legacy mode: Set session using official Supabase API
                    client.auth.set_session(
                        access_token=access_token,
                        refresh_token=refresh_token
                    )
                    # Setze den Auth-Header für PostgREST
                    client.postgrest.auth(access_token)
                # Storage Auth: Manuell setzen, da nicht automatisch übertragen
                if access_token and access_token != 'managed-by-cookies':
                    if hasattr(client.storage, '_client') and hasattr(client.storage._client, 'headers'):
                        client.storage._client.headers["Authorization"] = f"Bearer {access_token}"
                
                # Storage Auth: Public policy allows read access for section_materials
                # App-level security ensures only authorized users get file paths
                
                # Prüfe ob Token refresh nötig ist (mit Race-Condition-Prevention)
                if hasattr(st.session_state.session, 'expires_at'):
                    expires_at = st.session_state.session.expires_at
                    current_time = int(time.time())
                    
                    # Wenn Token in weniger als 5 Minuten abläuft, refreshe es
                    if expires_at - current_time < 300:
                        # Lock für Token Refresh um Race Conditions zu verhindern
                        refresh_lock_key = f'token_refresh_lock_{st.session_state.get("user", {}).get("id", "unknown")}'
                        if refresh_lock_key not in st.session_state:
                            st.session_state[refresh_lock_key] = False
                        
                        if not st.session_state[refresh_lock_key]:
                            st.session_state[refresh_lock_key] = True
                            try:
                                new_session = client.auth.refresh_session()
                                if new_session and new_session.session:
                                    st.session_state.session = new_session.session
                                    print(f"Token erfolgreich refreshed für User")
                            except Exception as e:
                                print(f"Token refresh fehlgeschlagen: {e}")
                            finally:
                                st.session_state[refresh_lock_key] = False
                
            except Exception as e:
                print(f"Fehler beim Setzen der User-Session im Client: {e}")
        
        # Speichere Client im session_state
        st.session_state.user_supabase_client = client
    
    return st.session_state.user_supabase_client


def invalidate_user_client():
    """
    Entfernt den User-spezifischen Client aus dem session_state.
    Sollte beim Logout aufgerufen werden.
    """
    if 'user_supabase_client' in st.session_state:
        del st.session_state.user_supabase_client


def get_anon_supabase_client() -> Client:
    """
    Gibt einen anonymen Supabase Client zurück (ohne User-Session).
    Für öffentliche Operationen wie Login/Registrierung.
    
    Returns:
        Client: Anonymer Supabase Client
    """
    options = ClientOptions(
        postgrest_client_timeout=120,
        storage_client_timeout=120
    )
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY, options=options)


def get_service_supabase_client() -> Optional[Client]:
    """
    Gibt einen Service-Role Supabase Client zurück (umgeht RLS).
    Für Admin-Operationen und Backend-Aufgaben.
    VORSICHT: Dieser Client umgeht Row Level Security!
    
    Returns:
        Client: Service-Role Supabase Client oder None falls nicht konfiguriert
    """
    if not SUPABASE_SERVICE_ROLE_KEY:
        print("WARNUNG: Supabase Service Role Key nicht konfiguriert. Service Client kann nicht erstellt werden.")
        return None
    
    try:
        options = ClientOptions(
            postgrest_client_timeout=120,
            storage_client_timeout=120
        )
        service_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, options=options)
        print("Service Supabase Client erfolgreich erstellt (session-aware).")
        return service_client
    except Exception as e:
        print(f"FEHLER bei der Erstellung des Service Supabase Clients: {e}")
        return None