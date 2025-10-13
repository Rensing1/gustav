import streamlit as st
from utils.session_client import get_user_supabase_client
from utils.db.platform.feedback import get_all_feedback



# Check if user is logged in and is a teacher
if "user" not in st.session_state:
    st.error("Bitte melden Sie sich an.")
    st.stop()

if st.session_state.role != "teacher":
    st.error("Diese Seite ist nur für Lehrer zugänglich.")
    st.stop()

st.title("📊 Schüler-Feedback")
st.write("Übersicht über alle anonymen Rückmeldungen der Schüler")

# Fetch all feedback
feedback_list = get_all_feedback()  # FIX: Remove client parameter - uses session-based RPC

if not feedback_list:
    st.info("Noch kein Feedback vorhanden.")
else:
    # Filter options
    col1, col2 = st.columns([1, 3])
    
    with col1:
        filter_type = st.selectbox(
            "Filter nach Typ",
            ["Alle", "Unterricht", "Plattform"]
        )
    
    # Apply filter
    if filter_type != "Alle":
        filtered_feedback = [f for f in feedback_list if f["feedback_type"] == filter_type.lower()]
    else:
        filtered_feedback = feedback_list
    
    # Display metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Gesamt", len(feedback_list))
    with col2:
        unterricht_count = len([f for f in feedback_list if f["feedback_type"] == "unterricht"])
        st.metric("Unterricht", unterricht_count)
    with col3:
        plattform_count = len([f for f in feedback_list if f["feedback_type"] == "plattform"])
        st.metric("Plattform", plattform_count)
    
    st.divider()
    
    # Display feedback
    if filtered_feedback:
        for feedback in filtered_feedback:
            # Create a container for each feedback
            with st.container():
                # Header with type and date
                col1, col2 = st.columns([3, 1])
                with col1:
                    if feedback["feedback_type"] == "unterricht":
                        st.markdown("**📚 Feedback zum Unterricht**")
                    else:
                        st.markdown("**💻 Feedback zur Plattform**")
                
                with col2:
                    # Format date - simple string parsing to avoid datetime parsing issues
                    try:
                        # Extract date and time from ISO string
                        datetime_str = feedback["created_at"]
                        # Get the date and time part (before timezone info)
                        if 'T' in datetime_str:
                            date_part, time_part = datetime_str.split('T')
                            # Extract time without microseconds and timezone
                            time_clean = time_part.split('.')[0] if '.' in time_part else time_part.split('+')[0]
                            # Format as DD.MM.YYYY HH:MM
                            year, month, day = date_part.split('-')
                            hour, minute = time_clean.split(':')[:2]
                            date_str = f"{day}.{month}.{year} {hour}:{minute}"
                        else:
                            date_str = datetime_str
                    except:
                        # Fallback if parsing fails
                        date_str = feedback["created_at"][:16]  # Just show first 16 chars
                    
                    st.caption(date_str)
                
                # Message
                st.write(feedback["message"])
                
                st.divider()
    else:
        st.info(f"Kein Feedback vom Typ '{filter_type}' vorhanden.")

