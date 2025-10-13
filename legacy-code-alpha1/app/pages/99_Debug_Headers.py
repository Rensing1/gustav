"""Debug page to check nginx headers"""
import streamlit as st

st.title("🔍 Debug: Headers und Auth Status")

# Check st.context availability
if hasattr(st, 'context'):
    st.success("✅ st.context ist verfügbar")
    
    if hasattr(st.context, 'headers'):
        st.subheader("Headers:")
        
        # Show all headers
        headers_dict = dict(st.context.headers)
        
        # Look for auth headers
        auth_headers = {}
        for key, value in headers_dict.items():
            if any(x in key.lower() for x in ['user', 'auth', 'session', 'role', 'email']):
                auth_headers[key] = value
        
        if auth_headers:
            st.write("**Auth-relevante Headers:**")
            st.json(auth_headers)
        else:
            st.warning("Keine Auth-Headers gefunden")
        
        # Show all headers in expander
        with st.expander("Alle Headers anzeigen"):
            st.json(headers_dict)
    
    # Check cookies
    if hasattr(st.context, 'cookies'):
        st.subheader("Cookies:")
        cookies_dict = dict(st.context.cookies)
        
        if 'gustav_session' in cookies_dict:
            st.success(f"✅ Session Cookie gefunden: {cookies_dict['gustav_session'][:20]}...")
        else:
            st.warning("Kein gustav_session Cookie gefunden")
        
        with st.expander("Alle Cookies anzeigen"):
            st.json(cookies_dict)
else:
    st.error("❌ st.context ist nicht verfügbar")

# Check session state
st.subheader("Session State:")
if hasattr(st.session_state, 'user') and st.session_state.user:
    st.write("**User in session_state:**")
    st.json(st.session_state.user)
else:
    st.warning("Kein User in session_state")

# Check auth integration
st.subheader("Auth Integration Status:")
from utils.auth_integration import AuthIntegration
from utils.auth_session import AuthSession

auth_mode = AuthIntegration.detect_auth_mode()
st.write(f"**Auth Mode:** {auth_mode}")

current_user = AuthSession.get_current_user()
if current_user:
    st.success("✅ User erkannt:")
    st.json(current_user)
else:
    st.warning("❌ Kein User erkannt")

is_auth = AuthIntegration.is_authenticated()
st.write(f"**Authenticated:** {is_auth}")