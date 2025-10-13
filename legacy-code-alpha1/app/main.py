import streamlit as st
import time
import os
# KEIN 'from streamlit.navigation import Page' mehr nötig

# Import unified auth integration
from utils.auth_integration import AuthIntegration

# Keep legacy imports for sign_up (not yet migrated)
from auth import sign_up, get_user_role

# --- Seitenkonfiguration (MUSS ZUERST) ---
st.set_page_config(
    page_title="GUSTAV-Lernplattform",
    page_icon="assets/GUSTAV-Logo.png",
    layout="wide"
)

# Importiere Auth-Funktionen (Duplikat entfernen)
from utils.session_client import invalidate_user_client, get_anon_supabase_client, get_user_supabase_client

# --- Initialisierung des Session State mit Auth Integration ---
AuthIntegration.initialize_session()

# Additional UI state
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = 0  # 0 = Login, 1 = Registrieren
if 'show_registration_success' not in st.session_state:
    st.session_state.show_registration_success = False



# --- E-Mail Bestätigungs-Handler ---

# Prüfe verschiedene Bestätigungs-Parameter
confirmation_params = [
    st.query_params.get("type") == "signup",
    st.query_params.get("type") == "email_change", 
    "token" in st.query_params,
    "confirmation_token" in st.query_params,
    "access_token" in st.query_params and not st.session_state.user
]

if any(confirmation_params):
    # Prüfe auf Fehler
    if st.query_params.get("error"):
        st.error(f"❌ Fehler: {st.query_params.get('error_description', st.query_params.get('error'))}")
        # Clear query params nur bei Fehler
        st.query_params.clear()
    else:
        st.success("✅ E-Mail-Adresse erfolgreich bestätigt!")
        st.info("Sie können sich jetzt mit Ihren Zugangsdaten anmelden.")
        # Setze active_tab auf Login
        st.session_state.active_tab = 0
        # Clear query params bei success
        st.query_params.clear()

# --- Hauptlogik ---

# Debug: Log authentication status
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug(f"Auth mode detected: {AuthIntegration.detect_auth_mode()}")
logger.debug(f"Is authenticated: {AuthIntegration.is_authenticated()}")
if hasattr(st, 'context') and hasattr(st.context, 'headers'):
    logger.debug(f"Available headers: {list(dict(st.context.headers).keys())}")

if not AuthIntegration.is_authenticated():
    # Check auth mode
    auth_mode = AuthIntegration.detect_auth_mode()
    
    # In HttpOnly mode, nginx will handle the redirect automatically
    if auth_mode == "httponly":
        st.title("Willkommen bei GUSTAV 📚")
        st.markdown("### Die KI-gestützte Lernplattform")
        st.info("🔒 Bitte melden Sie sich an, um fortzufahren.")
        st.stop()
    
    # Legacy mode: Show built-in login form
    st.title("Willkommen bei GUSTAV 📚")
    st.markdown("### Die KI-gestützte Lernplattform")
    st.sidebar.info("Bitte melden Sie sich an oder registrieren Sie sich.")

    # Tab-Container mit manueller Kontrolle
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Login", key="tab_login", type="primary" if st.session_state.active_tab == 0 else "secondary", use_container_width=True):
            st.session_state.active_tab = 0
            st.session_state.show_registration_success = False
            st.rerun()
    
    with col2:
        if st.button("Registrieren", key="tab_signup", type="primary" if st.session_state.active_tab == 1 else "secondary", use_container_width=True):
            st.session_state.active_tab = 1
            st.rerun()
    
    st.divider()
    
    # --- Login Form ---
    if st.session_state.active_tab == 0:
        st.subheader("Anmelden")
        
        # Login-Form direkt anzeigen
        with st.form("login_form", clear_on_submit=False):
            login_email = st.text_input("E-Mail")
            login_password = st.text_input("Passwort", type="password")
            login_submit = st.form_submit_button("Anmelden")

            if login_submit:
                if not login_email or not login_password:
                    st.warning("Bitte E-Mail und Passwort eingeben.")
                else:
                    # Use unified auth integration
                    success, error_msg = AuthIntegration.login(login_email, login_password)
                    
                    if success:
                        st.success("Erfolgreich angemeldet!")
                        # Show auth mode in development
                        if st.session_state.get('auth_mode') == 'httponly':
                            st.caption("🔒 Sichere Cookie-Authentifizierung aktiv")
                        st.rerun() # Wichtig, um Navigation neu aufzubauen
                    else:
                        if "❌" not in error_msg:  # Avoid double error icons
                            st.error(f"Anmeldefehler: {error_msg}")
                        else:
                            st.error(error_msg)
                        
                        if "bestätigen" in error_msg.lower():
                            st.info("📧 Überprüfen Sie Ihr Postfach und klicken Sie auf den Bestätigungslink.")

    # --- Registrierungs Form ---
    elif st.session_state.active_tab == 1:
        st.subheader("Registrieren")
        
        # Zeige Erfolgsmeldung wenn vorhanden
        if st.session_state.show_registration_success:
            st.success("✅ Registrierung erfolgreich!")
            st.info("📬 Bitte überprüfen Sie Ihre E-Mail-Adresse und klicken Sie auf den Bestätigungslink, um Ihr Konto zu aktivieren.")
            st.markdown("---")
            st.markdown("Nach der Bestätigung können Sie sich anmelden.")
            if st.button("→ Zum Login wechseln", key="after_signup_login"):
                st.session_state.active_tab = 0
                st.session_state.show_registration_success = False
                st.rerun()
        else:
            # Info über erlaubte E-Mail-Domains
            st.info("📧 Die Registrierung ist nur mit einer schulischen E-Mail-Adresse (@gymalf.de) möglich.")
            
            # Formular immer anzeigen (einfachste Lösung)
            with st.form("signup_form", clear_on_submit=True):
                signup_email = st.text_input("E-Mail", placeholder="vorname.nachname@gymalf.de")
                signup_password = st.text_input("Passwort", type="password", help="Mindestens 6 Zeichen")
                signup_confirm_password = st.text_input("Passwort bestätigen", type="password")
                signup_submit = st.form_submit_button("Registrieren")

                if signup_submit:
                    if not signup_email or not signup_password or not signup_confirm_password:
                        st.warning("Bitte alle Felder ausfüllen.")
                    elif signup_password != signup_confirm_password:
                        st.error("Die Passwörter stimmen nicht überein.")
                    elif len(signup_password) < 6:
                        st.error("Das Passwort muss mindestens 6 Zeichen lang sein.")
                    elif not signup_email.lower().endswith('@gymalf.de'):
                        st.error("❌ Die Registrierung ist nur mit einer @gymalf.de E-Mail-Adresse möglich.")
                    else:
                        res = sign_up(signup_email, signup_password)
                        if res.get("error"):
                            st.error(f"Registrierungsfehler: {res['error']['message']}")
                        elif res.get("user"):
                            # Setze Flag für Erfolgsmeldung und bleibe im Tab
                            st.session_state.show_registration_success = True
                            st.rerun()
                        else:
                            st.error("Unbekannter Fehler bei der Registrierung.")


else:
    # --- Angemeldeter Zustand: Definiere und zeige Navigation ---
    # Handle SecureUserDict (httponly), dict, and object (legacy) user formats
    user = st.session_state.user
    # Add null check before accessing user attributes
    if user is None:
        # This shouldn't happen, but handle gracefully
        st.error("Session-Fehler. Bitte laden Sie die Seite neu.")
        st.stop()
    elif hasattr(user, 'email'):
        # SecureUserDict or legacy object with attributes
        user_email = user.email
    elif isinstance(user, dict):
        # Plain dict (shouldn't happen with new code, but safe fallback)
        user_email = user.get('email')
    else:
        user_email = "Unknown"
    st.sidebar.success(f"Angemeldet als: {user_email}")
    role_display = "Lehrer" if st.session_state.role == "teacher" else "Schüler" if st.session_state.role == "student" else st.session_state.role
    st.sidebar.write(f"Rolle: **{role_display}**")
    
    # Zeige Auth-Status (nur in Development oder bei expliziter Konfiguration)
    if os.getenv('SHOW_AUTH_STATUS', 'false').lower() == 'true' or os.getenv('ENVIRONMENT') == 'development':
        auth_status = AuthIntegration.get_auth_status_message()
        st.sidebar.caption(auth_status)

    # Definiere die Seitenpfade basierend auf der Rolle
    # Die Dateinamen (z.B. "0_Dashboard.py") bestimmen Titel und Icon,
    # es sei denn, sie werden in der Datei selbst mit st.set_page_config überschrieben.
    pages_for_role = []
    if st.session_state.role == 'teacher':
        pages_for_role = [
            "pages/0_Startseite.py",
            "pages/1_Kurse.py",
            "pages/2_Lerneinheiten.py",
            "pages/5_Schueler.py",
            "pages/6_Live-Unterricht.py",
            "pages/9_Feedback_einsehen.py"
        ]
    elif st.session_state.role == 'student':
        pages_for_role = [
            "pages/0_Startseite.py",
            "pages/3_Meine_Aufgaben.py",
            "pages/7_Wissensfestiger.py",
            "pages/8_Feedback_geben.py"
        ]
    else:
        st.sidebar.warning("Unbekannte Rolle.")
        # Fallback: Nur Dashboard anzeigen, wenn Rolle unbekannt aber User eingeloggt
        pages_for_role = ["pages/0_Startseite.py"]

    # Rufe st.navigation mit der Liste der Pfade auf
    if pages_for_role:
        pg = st.navigation(pages_for_role)

        # Logout Button in der Sidebar (nur wenn eingeloggt)
        if st.sidebar.button("Logout"):
            success, error_msg = AuthIntegration.logout()
            if success:
                st.session_state.active_tab = 0
                st.session_state.show_registration_success = False
                st.success("Erfolgreich abgemeldet.")
                st.rerun()
            elif error_msg:
                st.error(f"Logout-Fehler: {error_msg}")

        # Führe den Code der ausgewählten Seite aus
        pg.run()

    else:
         # Zeige eine Meldung, wenn keine Seiten für die Rolle definiert sind
         st.error("Für Ihre Rolle sind keine Seiten konfiguriert.")
         if st.sidebar.button("Logout"): # Logout auch hier anbieten
            success, error_msg = AuthIntegration.logout()
            if success:
                st.session_state.active_tab = 0
                st.session_state.show_registration_success = False
                st.success("Erfolgreich abgemeldet.")
                st.rerun()
            elif error_msg:
                st.error(f"Logout-Fehler: {error_msg}")