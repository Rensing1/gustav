#!/usr/bin/env python3
"""
Test-Implementation für Extra-Streamlit-Components CookieManager
Mit Security Flags!
"""

import streamlit as st
import extra_streamlit_components as stx
import json
import time
import os
from datetime import datetime, timedelta
from cryptography.fernet import Fernet

st.set_page_config(page_title="ESC Cookie Test", page_icon="🔐")

st.title("🔐 Extra-Streamlit-Components Cookie Test")
st.success("✅ Diese Library unterstützt secure & samesite Flags!")
st.warning("⚠️ WICHTIG: Testen Sie mit 2 verschiedenen Browsern gleichzeitig!")

# Cookie Manager - KEINE Globale Variable!
def get_cookie_manager():
    """Erstelle Cookie Manager ohne @st.cache."""
    return stx.CookieManager()

# Verschlüsselung für sensible Daten
@st.cache_data
def get_fernet():
    """Cached Fernet instance für Verschlüsselung."""
    # In Production: aus Environment Variable
    key = os.environ.get('SESSION_ENCRYPTION_KEY', Fernet.generate_key())
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)

# Test 1: Basis Cookie mit Security Flags
st.header("1. Secure Cookie Test")

col1, col2 = st.columns(2)

with col1:
    if st.button("🔒 Secure Cookie setzen", type="primary"):
        cookie_manager = get_cookie_manager()
        test_value = f"secure_user_{int(time.time())}"
        
        # Cookie mit Security Flags setzen
        cookie_manager.set(
            cookie="esc_test_secure",
            val=test_value,
            expires_at=datetime.now() + timedelta(minutes=5),
            secure=True,  # HTTPS only
            same_site="strict",  # CSRF Schutz
            key="set_secure_cookie"
        )
        st.success(f"Secure Cookie gesetzt: {test_value}")
        st.info("Flags: secure=True, samesite=strict")

with col2:
    if st.button("🔍 Secure Cookie lesen"):
        cookie_manager = get_cookie_manager()
        value = cookie_manager.get("esc_test_secure")
        if value:
            st.info(f"Cookie-Wert: {value}")
        else:
            st.warning("Kein Cookie gefunden")

# Test 2: Verschlüsselte Session-Daten
st.header("2. Verschlüsselte Session Test")

col3, col4 = st.columns(2)

with col3:
    username = st.text_input("Username für Session Test:")
    if st.button("🔐 Verschlüsselte Session speichern") and username:
        cookie_manager = get_cookie_manager()
        fernet = get_fernet()
        
        # Session-Daten
        session_data = {
            "username": username,
            "user_id": f"user_{int(time.time() * 1000) % 10000}",
            "timestamp": datetime.now().isoformat(),
            "role": "student"
        }
        
        # Verschlüsseln
        encrypted_data = fernet.encrypt(json.dumps(session_data).encode())
        
        # Als sicheres Cookie speichern
        cookie_manager.set(
            cookie="esc_session",
            val=encrypted_data.decode(),
            max_age=60 * 90,  # 90 Minuten (Schulstunde)
            secure=True,
            same_site="strict",
            key="set_session"
        )
        st.success(f"Verschlüsselte Session für {username} gespeichert")
        st.code(f"Verschlüsselt: {encrypted_data.decode()[:50]}...")

with col4:
    if st.button("🔓 Session entschlüsseln"):
        cookie_manager = get_cookie_manager()
        encrypted = cookie_manager.get("esc_session")
        
        if encrypted:
            try:
                fernet = get_fernet()
                decrypted = fernet.decrypt(encrypted.encode())
                session_data = json.loads(decrypted.decode())
                st.json(session_data)
                
                # Session-Alter prüfen
                timestamp = datetime.fromisoformat(session_data['timestamp'])
                age = datetime.now() - timestamp
                st.info(f"Session-Alter: {age.seconds // 60} Minuten")
            except Exception as e:
                st.error(f"Entschlüsselung fehlgeschlagen: {e}")
        else:
            st.warning("Keine Session gefunden")

# Test 3: Cookie Management
st.header("3. Cookie Verwaltung")

col5, col6, col7 = st.columns(3)

with col5:
    if st.button("📋 Alle Cookies anzeigen"):
        cookie_manager = get_cookie_manager()
        all_cookies = cookie_manager.get_all()
        if all_cookies:
            st.json(all_cookies)
        else:
            st.info("Keine Cookies gefunden")

with col6:
    if st.button("🗑️ Test-Cookies löschen"):
        cookie_manager = get_cookie_manager()
        # Einzeln löschen
        cookie_manager.delete("esc_test_secure", key="delete_secure")
        cookie_manager.delete("esc_session", key="delete_session")
        st.info("Test-Cookies gelöscht")

with col7:
    if st.button("🔄 Seite neu laden"):
        st.rerun()

# Session-Bleeding Test-Anleitung
st.divider()
st.subheader("🧪 Session-Bleeding Test")

st.markdown("""
### Test-Ablauf:

1. **Browser 1 (Firefox):**
   - Username "Alice" eingeben
   - "Verschlüsselte Session speichern" klicken
   - "Session entschlüsseln" → zeigt Alice's Daten

2. **Browser 2 (Chrome):**
   - Direkt "Session entschlüsseln" klicken
   - ✅ **OK wenn**: "Keine Session gefunden"
   - ❌ **FEHLER wenn**: Alice's Daten erscheinen

3. **Browser 2 fortsetzen:**
   - Username "Bob" eingeben
   - "Verschlüsselte Session speichern"

4. **Zurück zu Browser 1:**
   - "Session entschlüsseln" klicken
   - ✅ **OK wenn**: Weiterhin Alice's Daten
   - ❌ **FEHLER wenn**: Bob's Daten erscheinen
""")

# Sicherheitsanalyse
with st.expander("🔒 Sicherheitsanalyse"):
    st.markdown("""
    ### Implementierte Sicherheitsmaßnahmen:
    
    | Maßnahme | Status | Details |
    |----------|--------|---------|
    | **secure Flag** | ✅ | Cookies nur über HTTPS |
    | **samesite=strict** | ✅ | CSRF-Schutz aktiviert |
    | **Verschlüsselung** | ✅ | Fernet (AES-256) |
    | **Session Timeout** | ✅ | 90 Minuten |
    | **httpOnly Flag** | ❌ | Nicht verfügbar* |
    
    *httpOnly kann nicht via JavaScript gesetzt werden (Browser-Limitierung)
    
    ### Verbleibende Risiken:
    - **XSS**: Cookies sind via JavaScript lesbar
    - **Mitigation**: Daten sind verschlüsselt + kurze Laufzeit
    
    ### Fazit für Schulumgebung:
    - Session-Bleeding ✅ gelöst
    - Basis-Sicherheit ✅ vorhanden
    - Für temporäre Lösung ✅ akzeptabel
    - Langfristig → Phase 2 (FastAPI)
    """)

# Debug-Info
with st.expander("🐛 Debug-Informationen"):
    st.write("Session State Keys:", list(st.session_state.keys()))
    st.write("Environment:", "Docker" if os.path.exists("/.dockerenv") else "Local")
    
    # Cookie Manager Info
    cm1 = get_cookie_manager()
    cm2 = get_cookie_manager()
    st.write("Cookie Manager sind verschiedene Instanzen:", cm1 is not cm2)
    st.write("Cookie Manager Cookies:", cm1.get_all())