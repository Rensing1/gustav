import streamlit as st
import requests
from datetime import datetime



from streamlit import session_state as state

# --- Zugriffskontrolle ---
if 'user' not in state or state.user is None:
    st.warning("Bitte zuerst anmelden, um die Startseite zu sehen.")
    st.stop()

# --- Seitenkonfiguration und Titel ---
st.title("🏠 Startseite")

# --- Willkommensnachricht ---
user = state.user
display_name = user.email.split('@')[0].replace('.', ' ').title() if user else 'Unbekannt'
role_display = "Lehrer" if state.role == 'teacher' else "Schüler" if state.role == 'student' else state.role

st.markdown(f"### Herzlich willkommen, {display_name}!")

# --- Alpha-Tester Hinweis ---
st.error("""
🧪 **Alpha-Version**: Sie testen die frühe Entwicklungsphase von GUSTAV!

Diese Version enthält experimentelle Funktionen und ist noch nicht vollständig ausgereift. 
**Ihr Feedback ist entscheidend** für die Weiterentwicklung der Plattform.

Bitte nutzen Sie das Modul „Feedback geben" um Ihre Erfahrungen, Probleme und Verbesserungsvorschläge zu teilen!
""")

st.divider()

# --- Plattform-Beschreibung ---
st.markdown("## 📚 Über GUSTAV")
st.markdown("""
GUSTAV ist eine **KI-gestützte Lernplattform**, die den Unterricht bereichern und den Lernerfolg steigern soll. Die Plattform ist experimentell und wird laufend basierend auf Ihrem Feedback weiterentwickelt. Bitte nutzen Sie das Modul „Feedback geben“, um Lob, Kritik und Verbesserungsvorschläge einzureichen. Das Feedback ist anonym.
""")

# --- Feature-Übersicht ---
if state.role == 'student':
    st.divider()
    st.markdown("## ✨ Hauptfunktionen")
    # Schüler-spezifische Features mit wissenschaftlichem Hintergrund
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 🤖 Automatisierte Rückmeldung")
        st.markdown("""
        **Intelligentes KI-Feedback** zu Ihren Lösungen, das konstruktiv formuliert ist und Verbesserungsmöglichkeiten aufzeigt.
        
        *Wissenschaftlich fundiert durch Erkenntnisse aus der 
        Feedback-Forschung (Hattie & Timperley, 2007)*
        """)
    
    with col2:
        st.markdown("### 🧠 Wissensfestiger")
        st.markdown("""
        **Nachhaltiges Lernen** durch Active Recall und Spaced Repetition – 
        bewährte Methoden zur Verankerung von Wissen im Langzeitgedächtnis.
        
        *Basiert auf der Vergessenskurve (Ebbinghaus) und 
        Retrieval Practice (Roediger & Butler, 2011)*
        """)
    
    with col3:
        st.markdown("### 💬 Rückmeldungen an Lehrer")
        st.markdown("""
        **Direkter Feedback-Kanal** um Verständnisprobleme, Wünsche und 
        Anregungen mit Ihren Lehrern zu teilen.
        
        *Durch Ihre Rückmeldung kann die Plattform verbessert werden.*
        """)

st.divider()

# --- Support/Hilfe ---
st.markdown("## 💡 Hilfe & Support")

col1, col2 = st.columns(2)

with col1:
    st.info("""
    **Erste Schritte:**
    - Am linken Rand finden Sie eine ausklappbare Navigationsleiste.
    - Unter "Meine Aufgaben" finden Sie den Unterrichtsbereich.
    - Unter "Wissensfestiger" können Sie das Karteikartenmodul nutzen.
    - Wählen Sie, sobald Sie auf der jeweiligen Seite sind, in der Navigationsleiste Ihren Kurs und ggf. die Lerneinheit aus.
    """)

with col2:
    st.info("""
    **Technische Hinweise:**
    - Aktuelle Version von Firefox empfohlen
    - Stabile Internetverbindung erforderlich
    - Bei Problemen Seite neu laden (F5)
    """)

st.divider()

# --- Datenschutzhinweis ---
st.markdown("## 🔒 Datenschutz")
st.info(
    """
    **Datenschutz ist uns wichtig.**
    Alle Daten werden datenschutzkonform auf Servern in Deutschland gespeichert und verarbeitet. 
    Es werden keine personenbezogenen Daten an Dritte weitergegeben.
    """
)

st.divider()

# --- Systemstatus ---
st.markdown("## 🔧 Systemstatus")

col1, col2, col3 = st.columns(3)

# Webapp Status (immer grün wenn die Seite lädt)
with col1:
    st.text("Webapp")
    st.caption("Online ✅")

# Datenbank Status (implizit durch erfolgreichen Login)
with col2:
    st.text("Datenbank")
    st.caption("Online ✅")

# Ollama Status prüfen
with col3:
    try:
        response = requests.get("http://ollama:11434/api/tags", timeout=2)
        if response.status_code == 200:
            st.text("KI-Service")
            st.caption("Online ✅")
        else:
            st.text("KI-Service")
            st.caption("Fehler ⚠️")
    except:
        st.text("KI-Service")
        st.caption("Offline ❌")

st.caption(f"Stand: {datetime.now().strftime('%d.%m.%Y %H:%M')} Uhr")
