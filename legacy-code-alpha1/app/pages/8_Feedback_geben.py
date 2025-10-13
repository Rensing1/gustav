import streamlit as st
from utils.session_client import get_user_supabase_client
from utils.db_queries import submit_feedback



# Check if user is logged in and is a student
if "user" not in st.session_state:
    st.error("Bitte melden Sie sich an.")
    st.stop()

if st.session_state.role != "student":
    st.error("Diese Seite ist nur für Schüler zugänglich.")
    st.stop()

st.title("💬 Feedback geben")
st.write("Teile uns anonym deine Rückmeldungen mit. Dein Feedback hilft uns, besser zu werden!")

# Show success message if feedback was submitted
if "feedback_submitted" in st.session_state and st.session_state.feedback_submitted:
    st.success("Vielen Dank für dein Feedback! Es wurde erfolgreich übermittelt.")
    # Reset the flag
    st.session_state.feedback_submitted = False

# Feedback form
with st.form("feedback_form", clear_on_submit=True):
    feedback_type = st.radio(
        "Worauf bezieht sich dein Feedback?",
        ["Unterricht", "Plattform"],
        help="Wähle aus, ob sich dein Feedback auf den Unterricht oder die GUSTAV-Plattform bezieht."
    )
    
    message = st.text_area(
        "Deine Nachricht",
        placeholder="Schreibe hier dein Feedback...",
        height=200,
        help="Dein Feedback wird anonym gespeichert. Sei ehrlich und konstruktiv!"
    )
    
    submitted = st.form_submit_button("Feedback absenden", type="primary")
    
    if submitted:
        if not message.strip():
            st.error("Bitte gib eine Nachricht ein.")
        else:
            # Convert to lowercase for database
            feedback_type_db = feedback_type.lower()
            
            # Use RPC function for session-based auth (HttpOnly cookies)
            success = submit_feedback(feedback_type_db, message.strip())
            
            if success:
                # Set flag for success message
                st.session_state.feedback_submitted = True
                # Trigger rerun to show success message and clear form
                st.rerun()
            else:
                st.error("Beim Absenden ist ein Fehler aufgetreten. Bitte versuche es später erneut.")

# Info box
with st.expander("ℹ️ Über das Feedback-System"):
    st.write("""
    **Dein Feedback ist uns wichtig!**
    
    - Alle Rückmeldungen sind **vollständig anonym**
    - Deine Lehrer können sehen, was geschrieben wurde, aber nicht von wem
    - Nutze diese Möglichkeit, um konstruktive Verbesserungsvorschläge zu machen
    - Sowohl Lob als auch Kritik sind willkommen
    
    **Feedback-Arten:**
    - **Unterricht**: Rückmeldungen zu Unterrichtsmethoden, Aufgaben, Tempo, etc.
    - **Plattform**: Vorschläge zur GUSTAV-Plattform, technische Probleme, neue Features
    """)