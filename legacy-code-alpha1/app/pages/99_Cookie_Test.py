#!/usr/bin/env python3
"""
Test-Implementation für streamlit-cookies-controller
WICHTIG: Multi-Browser-Tests durchführen!
"""

import streamlit as st
from streamlit_cookies_controller import CookieController
import json
import time
import os
from datetime import datetime

st.set_page_config(page_title="Cookie Test", page_icon="🍪")

st.title("🍪 Cookie Controller Test")
st.warning("⚠️ WICHTIG: Testen Sie mit 2 verschiedenen Browsern gleichzeitig!")
st.error("🚨 SICHERHEITSWARNUNG: streamlit-cookies-controller unterstützt KEINE Security-Flags (httpOnly, secure, samesite)! Cookies sind via JavaScript zugreifbar!")

# KEINE globalen Variablen, KEIN Caching!
def get_cookie_controller():
    """Erstelle neue Instanz für jeden Request - verhindert Session-Bleeding."""
    return CookieController()

# Test 1: Basis-Funktionalität
st.header("1. Basis Cookie Test")

col1, col2 = st.columns(2)

with col1:
    if st.button("🔵 Cookie setzen", type="primary"):
        controller = get_cookie_controller()
        test_value = f"user_{int(time.time())}"
        controller.set("test_cookie", test_value)
        # HINWEIS: streamlit-cookies-controller unterstützt keine erweiterten Parameter!
        st.success(f"Cookie gesetzt: {test_value}")

with col2:
    if st.button("🔍 Cookie lesen"):
        controller = get_cookie_controller()
        value = controller.get("test_cookie")
        if value:
            st.info(f"Cookie-Wert: {value}")
        else:
            st.warning("Kein Cookie gefunden")

# Test 2: Session-ähnliche Daten
st.header("2. Session-Daten Test")

col3, col4 = st.columns(2)

with col3:
    username = st.text_input("Username für Test:")
    if st.button("📝 Session speichern") and username:
        controller = get_cookie_controller()
        session_data = {
            "username": username,
            "timestamp": datetime.now().isoformat(),
            "browser_id": f"browser_{int(time.time() * 1000) % 10000}"
        }
        controller.set("test_session", json.dumps(session_data))
        # Keine Security-Flags verfügbar - KRITISCH für Production!
        st.success(f"Session gespeichert für: {username}")

with col4:
    if st.button("👤 Session laden"):
        controller = get_cookie_controller()
        session_str = controller.get("test_session")
        if session_str:
            try:
                session_data = json.loads(session_str)
                st.json(session_data)
            except:
                st.error("Fehler beim Parsen der Session-Daten")
        else:
            st.warning("Keine Session gefunden")

# Test 3: Cookie löschen
st.header("3. Cookie Löschen")
if st.button("🗑️ Alle Test-Cookies löschen", type="secondary"):
    controller = get_cookie_controller()
    controller.remove("test_cookie")
    controller.remove("test_session")
    st.info("Test-Cookies gelöscht")

# Test-Anleitung
st.divider()
st.subheader("🧪 Test-Anleitung für Session-Bleeding")

st.markdown("""
1. **Browser 1 (z.B. Firefox):**
   - Username "Alice" eingeben
   - "Session speichern" klicken
   - "Session laden" klicken → sollte Alice anzeigen

2. **Browser 2 (z.B. Chrome):**
   - OHNE einzuloggen: "Session laden" klicken
   - ❌ **FEHLER wenn**: Alice's Daten erscheinen
   - ✅ **OK wenn**: "Keine Session gefunden"

3. **Browser 2 fortsetzung:**
   - Username "Bob" eingeben
   - "Session speichern" klicken
   
4. **Zurück zu Browser 1:**
   - "Session laden" klicken
   - ❌ **FEHLER wenn**: Bob's Daten erscheinen
   - ✅ **OK wenn**: Weiterhin Alice's Daten

**Wenn Session-Bleeding auftritt:** SOFORT ABBRECHEN!
""")

# Debug-Info
with st.expander("🐛 Debug-Informationen"):
    st.write("Session State Keys:", list(st.session_state.keys()))
    # Sicherer Check ohne Fehler
    try:
        in_docker = st.secrets.get("IN_DOCKER", False)
    except:
        in_docker = os.path.exists("/.dockerenv")
    st.write("Script läuft in:", "Docker" if in_docker else "Local")
    
    # Test ob Controller neue Instanz ist
    controller1 = get_cookie_controller()
    controller2 = get_cookie_controller()
    st.write("Controller sind verschiedene Instanzen:", controller1 is not controller2)