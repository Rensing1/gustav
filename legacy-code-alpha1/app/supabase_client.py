# app/supabase_client.py
# DEPRECATED: This module is deprecated in favor of utils/session_client.py
# The @st.cache_resource decorators in this file caused session bleeding between users.
# This file is kept for rollback purposes only.
# Use utils/session_client.py instead for session-aware Supabase clients.

import streamlit as st
# --- KORREKTUR: ClientOptions importieren ---
from supabase import create_client, Client, ClientOptions
# --- KORREKTUR: Importiere Konfigurationswerte statt os und load_dotenv ---
from config import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY

# Prüfe, ob die Variablen aus config geladen wurden
# (Die Validierung in config.py sollte dies bereits sicherstellen)
if not SUPABASE_URL or not SUPABASE_ANON_KEY:
     # Dieser Fehler sollte dank der Prüfung in config.py nicht mehr auftreten,
     # aber als zusätzliche Sicherheitsebene hier belassen.
     st.error("Supabase URL oder Anon Key nicht konfiguriert! Prüfe config.py und .env.")
     print("FATAL ERROR: Supabase URL oder Anon Key nicht via config.py verfügbar.")
     st.stop()

# --- Standard Client (Anon Key) ---
# REMOVED @st.cache_resource to prevent session bleeding
def get_supabase_client() -> Client:
    """Initialisiert und gibt eine Supabase Client Instanz (Anon Key) zurück."""
    try:
        # Verwende die erhöhten Timeouts
        options = ClientOptions(postgrest_client_timeout=120, storage_client_timeout=120)
        # --- KORREKTUR: Verwende die importierten Variablen ---
        client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY, options=options)
        print("Supabase Anon Client erfolgreich initialisiert.")
        return client
    except Exception as e:
        st.error(f"Fehler bei der Initialisierung des Supabase Anon Clients: {e}")
        print(f"Fehler bei der Initialisierung des Supabase Anon Clients: {e}")
        st.stop()

# REMOVED global client variable to prevent session bleeding
# supabase_client: Client = get_supabase_client()

# --- Service Role Client ---
# REMOVED @st.cache_resource to prevent session bleeding
def get_supabase_service_client() -> Client | None:
    """
    Initialisiert und gibt eine Supabase Client Instanz (Service Role Key) zurück.
    Gibt None zurück, wenn der Service Key nicht konfiguriert ist.
    VORSICHT: Dieser Client umgeht RLS! Nur für Backend/Admin-Aufgaben verwenden.
    """
    # --- KORREKTUR: Prüfe importierte Variable ---
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
         print("WARNUNG: Supabase Service Role Key nicht via config.py verfügbar. Service Client kann nicht erstellt werden.")
         return None
    try:
        options = ClientOptions(postgrest_client_timeout=120, storage_client_timeout=120)
        # --- KORREKTUR: Verwende die importierten Variablen ---
        service_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, options=options)
        print("Supabase Service Client erfolgreich initialisiert.")
        return service_client
    except Exception as e:
        print(f"FEHLER bei der Initialisierung des Supabase Service Clients: {e}")
        return None

# Debugging-Ausgabe (optional)
# print(f"Supabase URL (aus config): {SUPABASE_URL}")