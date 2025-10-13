import streamlit as st
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from supabase import Client
from utils.session_client import get_user_supabase_client, get_anon_supabase_client, invalidate_user_client

# Constants
MIN_PASSWORD_LENGTH = 6

# @st.cache_data(ttl=600) # <<< DIESE ZEILE ENTFERNEN ODER AUSKOMMENTIEREN
def get_user_role(_user_id: str) -> str | None:
    """Fragt die Rolle des Nutzers aus der 'profiles' Tabelle ab."""
    if not _user_id:
        return None
    try:
        client = get_user_supabase_client()
        response = client.table('profiles').select('role').eq('id', _user_id).single().execute()
        if hasattr(response, 'error') and response.error:
             print(f"Fehler beim Abrufen der Nutzerrolle: {response.error.message}")
             st.error(f"Fehler beim Laden der Rolle: {response.error.message}") # st.error braucht state oder st
             return None
        elif response.data:
            return response.data.get('role')
        else:
            print(f"Kein Profil für User ID {_user_id} gefunden.")
            st.warning(f"Profil für User ID {_user_id} nicht gefunden.")
            return None
    except Exception as e:
        st.error(f"Unerwarteter Fehler beim Abrufen der Nutzerrolle: {e}") # st.error braucht state oder st
        print(f"Exception beim Abrufen der Nutzerrolle: {e}")
        return None

def sign_up(email, password):
    """Registriert einen neuen Nutzer bei Supabase Auth.
       Das Profil wird automatisch durch einen DB-Trigger erstellt.
       Gibt immer ein Dictionary zurück: {'user': User|None, 'session': Session|None, 'error': dict|None}"""
    try:
        # Verwende anonymen Client für Registrierung
        client = get_anon_supabase_client()
        auth_response = client.auth.sign_up({"email": email, "password": password})
        print(f"Auth Signup Response: {auth_response}")

        # Auth Fehler prüfen
        if hasattr(auth_response, 'error') and auth_response.error:
            print(f"Auth Signup Error: {auth_response.error.message}")
            return {"user": None, "session": None, "error": {"message": auth_response.error.message}}
        elif auth_response and auth_response.user:
             # Erfolg (Profil wird durch Trigger erstellt)
             print(f"Auth Signup für {email} erfolgreich. Profil wird durch Trigger erstellt.")
             return {"user": auth_response.user, "session": auth_response.session, "error": None}
        else:
             # Unerwarteter Fall
             print("Auth Signup erfolgreich, aber kein User-Objekt zurückgegeben.")
             return {"user": None, "session": None, "error": {"message": "Registrierung fehlgeschlagen (Auth-Benutzer nicht gefunden)."}}

    except Exception as auth_e: # Fehler während Auth Call
        print(f"Exception during Auth Signup: {auth_e}")
        return {"user": None, "session": None, "error": {"message": f"Fehler bei Auth-Registrierung: {auth_e}"}}

def sign_in(email, password):
    """Meldet einen Nutzer an.
       Gibt immer ein Dictionary zurück: {'user': User|None, 'session': Session|None, 'error': dict|None}"""
    try:
        # Verwende anonymen Client für Login
        client = get_anon_supabase_client()
        res = client.auth.sign_in_with_password({"email": email, "password": password})
        print(f"Sign In Response: {res}") # Debugging

        # Fehler prüfen
        if hasattr(res, 'error') and res.error:
             print(f"Sign In Error: {res.error.message}")
             return {"user": None, "session": None, "error": {"message": res.error.message}}
        elif res.user and res.session:
             # Erfolg
             return {"user": res.user, "session": res.session, "error": None}
        else:
             # Unerwartete Antwort
             print(f"Sign In unexpected response: {res}")
             return {"user": None, "session": None, "error": {"message": "Anmeldung fehlgeschlagen (unerwartete Antwort)."}}

    except Exception as e: # Genereller Fehler
        print(f"Exception during Sign In: {e}")
        return {"user": None, "session": None, "error": {"message": f"Fehler bei Anmeldung: {e}"}}

def sign_out():
    """Meldet den aktuellen Nutzer ab."""
    try:
        client = get_user_supabase_client()
        client.auth.sign_out()
        # Invalidiere den User-Client
        invalidate_user_client()
        return True
    except Exception as e:
        st.error(f"Unerwarteter Fehler bei der Abmeldung: {e}")
        print(f"Exception bei Abmeldung: {e}")
        return False

def get_user():
     """Holt den aktuellen Nutzer anhand des gespeicherten Tokens."""
     try:
          client = get_user_supabase_client()
          user_response = client.auth.get_user()
          if hasattr(user_response, 'error') and user_response.error:
              print(f"Fehler beim Abrufen des Nutzers: {user_response.error.message}")
              return None
          return user_response.user if user_response else None
     except Exception as e:
          print(f"Fehler beim Abrufen des Nutzers: {e}")
          return None


