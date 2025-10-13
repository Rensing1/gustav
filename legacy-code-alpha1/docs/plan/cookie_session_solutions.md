# Cookie-basierte Session-Management Lösungen für GUSTAV

**Datum:** 2025-01-09  
**Status:** LÖSUNGSVORSCHLÄGE  
**Priorität:** KRITISCH

## Problem-Zusammenfassung

- Streamlit Session State ist RAM-basiert → F5 = Logout
- LocalStorage ist domain-global → Session-Bleeding
- nginx auth_request inkompatibel mit Streamlit WebSockets
- st.context kann nur Cookies LESEN, nicht SETZEN

## LÖSUNG 1: Streamlit-Cookies-Controller (EMPFOHLEN)

### Übersicht
Nutze die `streamlit-cookies-controller` Library (April 2024) für Cookie-Management direkt in Streamlit.

### Technische Umsetzung

```python
# app/utils/cookie_session.py
import streamlit as st
from streamlit_cookies_controller import CookieController
from cryptography.fernet import Fernet
import json
import time
from datetime import datetime, timedelta
import os

class CookieSessionManager:
    def __init__(self):
        self.controller = CookieController()
        self.cookie_name = "gustav_session"
        self.encryption_key = os.environ.get('SESSION_ENCRYPTION_KEY', Fernet.generate_key())
        self.fernet = Fernet(self.encryption_key)
        self.max_age = 90 * 60  # 90 Minuten
        
    def save_session(self, user_data, session_data):
        """Speichert verschlüsselte Session in Cookie."""
        session_payload = {
            'user_id': user_data.id,
            'email': user_data.email,
            'access_token': session_data.access_token,
            'refresh_token': session_data.refresh_token,
            'expires_at': session_data.expires_at,
            'created_at': time.time(),
            'role': get_user_role(user_data.id)
        }
        
        # Verschlüsseln
        encrypted = self.fernet.encrypt(json.dumps(session_payload).encode())
        
        # Cookie setzen mit 90 Minuten Laufzeit
        self.controller.set(
            self.cookie_name, 
            encrypted.decode(),
            max_age=self.max_age,
            httponly=True,      # XSS-Schutz
            secure=True,        # HTTPS only
            samesite='strict'   # CSRF-Schutz
        )
        
    def restore_session(self):
        """Lädt und validiert Session aus Cookie."""
        try:
            encrypted_data = self.controller.get(self.cookie_name)
            if not encrypted_data:
                return None
                
            # Entschlüsseln
            decrypted = self.fernet.decrypt(encrypted_data.encode())
            session_data = json.loads(decrypted.decode())
            
            # Timeout prüfen
            if time.time() - session_data['created_at'] > self.max_age:
                self.clear_session()
                return None
                
            # Token-Gültigkeit prüfen
            if time.time() > session_data['expires_at']:
                # Token refresh hier
                return self._refresh_token(session_data)
                
            return session_data
            
        except Exception as e:
            logger.error(f"Session restore failed: {e}")
            return None
            
    def clear_session(self):
        """Löscht Session-Cookie."""
        self.controller.remove(self.cookie_name)
```

### Integration in main.py

```python
# app/main.py - Minimale Änderungen
from utils.cookie_session import CookieSessionManager

# Vor Login-Check
if 'user' not in st.session_state:
    cookie_manager = CookieSessionManager()
    session_data = cookie_manager.restore_session()
    
    if session_data:
        # Session wiederherstellen
        st.session_state.user = recreate_user_object(session_data)
        st.session_state.session = recreate_session_object(session_data)
        st.session_state.role = session_data['role']
        # KEIN st.rerun() nötig!
    else:
        # Normaler Login-Flow
        show_login_form()
        
# Nach erfolgreichem Login
if login_successful:
    cookie_manager.save_session(user, session)
```

### Vorteile
✅ **Direkt in Streamlit** - keine externe Infrastruktur  
✅ **Browser-isolierte Cookies** - kein Session-Bleeding  
✅ **HttpOnly + Secure** - XSS/CSRF geschützt  
✅ **90 Minuten Persistenz** - überlebt F5  
✅ **Minimal invasiv** - wenige Code-Änderungen  

### Nachteile
⚠️ Zusätzliche Dependency  
⚠️ Community-Component (nicht offiziell)

### Zeitaufwand: 2-3 Stunden

---

## LÖSUNG 2: Supabase Custom Storage

### Übersicht
Konfiguriere Supabase Client für Cookie-basierte Session-Storage.

### Technische Umsetzung

```python
# app/utils/supabase_cookie_client.py
from supabase import create_client, Client
import streamlit as st
from streamlit_cookies_controller import CookieController
import json

class SupabaseCookieStorage:
    def __init__(self):
        self.controller = CookieController()
        self.cookie_name = "sb_session"
        
    async def get_item(self, key: str) -> str:
        """Get item from cookie storage."""
        data = self.controller.get(self.cookie_name)
        if data:
            parsed = json.loads(data)
            return parsed.get(key)
        return None
        
    async def set_item(self, key: str, value: str):
        """Set item in cookie storage."""
        data = self.controller.get(self.cookie_name)
        parsed = json.loads(data) if data else {}
        parsed[key] = value
        
        self.controller.set(
            self.cookie_name,
            json.dumps(parsed),
            max_age=60*60*24*7,  # 7 Tage
            httponly=True,
            secure=True,
            samesite='strict'
        )
        
    async def remove_item(self, key: str):
        """Remove item from cookie storage."""
        data = self.controller.get(self.cookie_name)
        if data:
            parsed = json.loads(data)
            parsed.pop(key, None)
            if parsed:
                self.controller.set(self.cookie_name, json.dumps(parsed))
            else:
                self.controller.remove(self.cookie_name)

def get_cookie_supabase_client() -> Client:
    """Create Supabase client with cookie storage."""
    storage = SupabaseCookieStorage()
    
    return create_client(
        SUPABASE_URL,
        SUPABASE_KEY,
        options={
            'auth': {
                'storage': storage,
                'persistSession': True,
                'autoRefreshToken': True
            }
        }
    )
```

### Vorteile
✅ **Native Supabase Integration** - nutzt eingebaute Features  
✅ **Automatisches Token-Refresh** - Supabase managed alles  
✅ **Konsistent mit Supabase Auth** - keine Custom-Logic  

### Nachteile
⚠️ Async Storage API kann Probleme machen  
⚠️ Mehr Komplexität in der Integration  

### Zeitaufwand: 4-6 Stunden

---

## LÖSUNG 3: Minimaler Hybrid-Ansatz

### Übersicht
Kleine FastAPI-App nur für Cookie-Management, Streamlit nutzt st.context zum Lesen.

### Technische Umsetzung

```python
# auth_api/main.py - Minimaler Cookie-Service
from fastapi import FastAPI, Response, Request
from fastapi.responses import RedirectResponse
import jwt
from datetime import datetime, timedelta

app = FastAPI()

@app.post("/api/auth/set-session")
async def set_session_cookie(
    response: Response,
    user_id: str,
    email: str,
    role: str,
    access_token: str,
    refresh_token: str
):
    """Called by Streamlit after successful login."""
    # Create JWT with session data
    session_jwt = jwt.encode({
        'user_id': user_id,
        'email': email,
        'role': role,
        'access_token': access_token,
        'refresh_token': refresh_token,
        'exp': datetime.utcnow() + timedelta(minutes=90)
    }, SECRET_KEY, algorithm='HS256')
    
    # Set HttpOnly cookie
    response.set_cookie(
        key="gustav_session",
        value=session_jwt,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=60*90  # 90 minutes
    )
    
    return {"status": "success"}

@app.post("/api/auth/clear-session")
async def clear_session_cookie(response: Response):
    """Clear session cookie."""
    response.delete_cookie("gustav_session")
    return {"status": "success"}
```

```python
# app/utils/hybrid_session.py
import streamlit as st
import requests
import jwt

def save_session_hybrid(user_data, session_data):
    """Save session via API call."""
    response = requests.post(
        "http://localhost:8000/api/auth/set-session",
        json={
            "user_id": user_data.id,
            "email": user_data.email,
            "role": get_user_role(user_data.id),
            "access_token": session_data.access_token,
            "refresh_token": session_data.refresh_token
        }
    )
    return response.status_code == 200

def restore_session_hybrid():
    """Restore session from cookie via st.context."""
    if hasattr(st.context, 'cookies'):
        cookie_data = st.context.cookies.get('gustav_session')
        if cookie_data:
            try:
                decoded = jwt.decode(cookie_data, SECRET_KEY, algorithms=['HS256'])
                return decoded
            except:
                pass
    return None
```

### nginx Config

```nginx
# Route API calls to FastAPI
location /api/auth/ {
    proxy_pass http://auth-api:8000/api/auth/;
}

# Streamlit app
location / {
    proxy_pass http://app:8501;
}
```

### Vorteile
✅ **Echte HttpOnly Cookies** - maximale Sicherheit  
✅ **Saubere Trennung** - Auth-Logic außerhalb Streamlit  
✅ **Keine WebSocket-Probleme** - nur API-Calls  

### Nachteile
⚠️ Zusätzlicher Service  
⚠️ Mehr Moving Parts  

### Zeitaufwand: 4-5 Stunden

---

## LÖSUNG 4: Service Worker + IndexedDB (Modern & Browser-Isoliert)

### Übersicht
Nutze moderne Browser-APIs für persistente, browser-isolierte Session-Speicherung ohne Cookies.

### Technische Umsetzung

```javascript
// static/sw.js - Service Worker
const CACHE_NAME = 'gustav-session-v1';

self.addEventListener('install', event => {
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(clients.claim());
});

// Intercept navigation requests
self.addEventListener('fetch', event => {
    if (event.request.mode === 'navigate') {
        event.respondWith(
            (async () => {
                // Check if we have a session
                const session = await getSessionFromIndexedDB();
                
                if (!session && !event.request.url.includes('/login')) {
                    // Redirect to login
                    return Response.redirect('/login', 302);
                }
                
                // Pass through with session headers
                const modifiedHeaders = new Headers(event.request.headers);
                if (session) {
                    modifiedHeaders.set('X-Session-Data', JSON.stringify(session));
                }
                
                return fetch(new Request(event.request, {
                    headers: modifiedHeaders
                }));
            })()
        );
    }
});

async function getSessionFromIndexedDB() {
    const db = await openDB('gustav-sessions', 1);
    const tx = db.transaction('sessions', 'readonly');
    const store = tx.objectStore('sessions');
    return await store.get('current');
}
```

```html
<!-- app/static/session-manager.html -->
<script>
// Register Service Worker
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js');
}

// Session Manager
class SessionManager {
    constructor() {
        this.dbName = 'gustav-sessions';
        this.storeName = 'sessions';
        this.initDB();
    }
    
    async initDB() {
        this.db = await this.openDB();
    }
    
    openDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, 1);
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                if (!db.objectStoreNames.contains(this.storeName)) {
                    db.createObjectStore(this.storeName);
                }
            };
            
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
    
    async saveSession(sessionData) {
        const tx = this.db.transaction([this.storeName], 'readwrite');
        const store = tx.objectStore(this.storeName);
        
        // Add expiry
        sessionData.expiresAt = Date.now() + (90 * 60 * 1000); // 90 minutes
        
        await store.put(sessionData, 'current');
        
        // Notify Streamlit
        window.parent.postMessage({
            type: 'session-saved',
            data: sessionData
        }, '*');
    }
    
    async getSession() {
        const tx = this.db.transaction([this.storeName], 'readonly');
        const store = tx.objectStore(this.storeName);
        const session = await store.get('current');
        
        if (session && session.expiresAt > Date.now()) {
            return session;
        }
        
        // Expired or not found
        await this.clearSession();
        return null;
    }
    
    async clearSession() {
        const tx = this.db.transaction([this.storeName], 'readwrite');
        const store = tx.objectStore(this.storeName);
        await store.delete('current');
    }
}

// Global instance
window.sessionManager = new SessionManager();

// Listen for Streamlit messages
window.addEventListener('message', async (event) => {
    if (event.data.type === 'save-session') {
        await window.sessionManager.saveSession(event.data.session);
    } else if (event.data.type === 'get-session') {
        const session = await window.sessionManager.getSession();
        event.source.postMessage({
            type: 'session-data',
            session: session
        }, event.origin);
    } else if (event.data.type === 'clear-session') {
        await window.sessionManager.clearSession();
    }
});
</script>
```

```python
# app/utils/service_worker_session.py
import streamlit as st
import streamlit.components.v1 as components
import json
import time

class ServiceWorkerSessionManager:
    def __init__(self):
        self.component_key = "session_manager"
        
    def _render_component(self):
        """Render the session manager component."""
        return components.html(
            open('static/session-manager.html').read(),
            height=0
        )
        
    def save_session(self, user_data, session_data):
        """Save session via Service Worker."""
        session_payload = {
            'userId': user_data.id,
            'email': user_data.email,
            'accessToken': session_data.access_token,
            'refreshToken': session_data.refresh_token,
            'expiresAt': session_data.expires_at,
            'role': get_user_role(user_data.id)
        }
        
        # Send to Service Worker
        self._render_component()
        components.html(f"""
        <script>
        window.sessionManager.saveSession({json.dumps(session_payload)});
        </script>
        """, height=0)
        
    def restore_session(self):
        """Restore session from Service Worker."""
        # This would need a callback mechanism
        # For simplicity, we'll use st.query_params as a bridge
        self._render_component()
        
        # Check if Service Worker passed session data
        if 'session_data' in st.query_params:
            try:
                session = json.loads(st.query_params['session_data'])
                st.query_params.pop('session_data')
                return session
            except:
                pass
                
        return None
```

### Vorteile
✅ **Modernste Technologie** - Service Workers + IndexedDB  
✅ **Browser-isoliert** - jeder Browser hat eigene DB  
✅ **Offline-fähig** - funktioniert ohne Server  
✅ **Keine Cookies** - umgeht Cookie-Limitierungen  
✅ **Persistent** - überlebt Browser-Restart  

### Nachteile
⚠️ Browser-Support (moderne Browser only)  
⚠️ Komplexere Implementation  
⚠️ Streamlit-Integration tricky  

### Zeitaufwand: 6-8 Stunden

---

## EMPFEHLUNG: Lösung 1 (Streamlit-Cookies-Controller)

**Warum?**
1. **Minimal invasiv** - passt in bestehende Architektur
2. **Schnell implementierbar** - 2-3 Stunden
3. **Battle-tested** - wird 2024 aktiv genutzt
4. **Keine neue Infrastruktur** - läuft in Streamlit

**Sofortige Schritte:**
```bash
pip install streamlit-cookies-controller
```

Dann Implementation wie oben beschrieben.

## Fallback-Plan

Falls Lösung 1 Probleme macht, ist Lösung 3 (Hybrid) der sauberste Ansatz für Production.

## Wichtige Sicherheitsaspekte

Egal welche Lösung:
- **HttpOnly** Flag setzen (XSS-Schutz)
- **Secure** Flag setzen (HTTPS only)
- **SameSite=Strict** (CSRF-Schutz)
- **Verschlüsselung** der Session-Daten
- **Kurze Laufzeiten** (90 Minuten für Schulstunden)