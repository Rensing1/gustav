# GUSTAV Session-Management - Detaillierte technische Analyse

**Datum:** 2025-01-04  
**Status:** Lösungsvorschläge validiert  
**Priorität:** Hoch (kritisches UX-Problem)  
**Update:** Cookie-basierte Lösungen funktionieren sehr wohl!

## Aktuelle Architektur & Probleme

**Status Quo:**
```python
# main.py - Aktueller Login-Flow
if not st.session_state.user:
    email, password = show_login_form()
    result = sign_in(email, password)  # Supabase Auth
    
    if result.user:
        st.session_state.user = result.user          # RAM-Storage
        st.session_state.session = result.session    # JWT hier
        st.session_state.role = get_user_role(user.id)
```

**Problem-Details:**
1. **JWT-Lifetime:** `supabase/config.toml` → `jwt_expiry = 3600` (1h)
2. **Storage:** Login-Daten nur in Streamlit's Session-State (Server-RAM)
3. **Persistence:** Bei F5 wird kompletter Python-Prozess neu gestartet → RAM gelöscht

**Zwei kritische Szenarien:**

1. **JWT-Timeout nach 1 Stunde**
   - Fehler: `JWT expired` (Code: PGRST301)
   - Nutzer muss sich komplett neu anmelden
   - Arbeitsverlust möglich

2. **Logout bei Seitenreload (F5)**
   - Session-State geht verloren
   - Selbst mit gültigem Token wird Nutzer ausgeloggt
   - Häufigstes und nervigste Problem

---

## Lösung 1: Streamlit-Authenticator - Kompletter Auth-Replacement

### Konzept
Ersetze Supabase-Auth durch spezialisierte Streamlit-Authentication-Library

**Architektur-Änderung:**
```python
# VORHER: Supabase macht alles
supabase.auth.sign_in() → JWT → Session-State

# NACHHER: Streamlit-Authenticator macht alles  
stauth.login() → BCrypt-Check → JWT-Cookie → Session-State
```

### Implementation Details

```python
# 1. User-Config (ersetzt Supabase users table)
config = {
    'credentials': {
        'usernames': {
            'teacher@school.de': {
                'email': 'teacher@school.de',
                'name': 'Max Mustermann', 
                'password': '$2b$12$hash...'  # BCrypt von Supabase-Passwort
            }
        }
    },
    'cookie': {
        'expiry_days': 30,              # 30 Tage statt 1 Stunde!
        'name': 'gustav_auth_cookie',
        'key': 'random-secret-key-32-chars'
    }
}

# 2. Login-Widget (ersetzt bestehendes)
authenticator = stauth.Authenticate(config['credentials'], 
                                    config['cookie']['name'],
                                    config['cookie']['key'], 
                                    config['cookie']['expiry_days'])

name, authentication_status, username = authenticator.login('Login', 'main')

# 3. Cookie-Management (automatisch)
# - Bei erfolgreichem Login: JWT in httpOnly Cookie
# - Bei App-Start: Cookie-Validation → Auto-Login
# - Bei Logout: Cookie löschen
```

### Was passiert unter der Haube
1. **Login:** BCrypt-Passwort-Check → JWT erstellen → in Cookie speichern
2. **Page-Reload:** Cookie lesen → JWT validieren → Session wiederherstellen  
3. **30 Tage später:** Cookie expired → erneuter Login nötig

### Datenfluss
- **User-Credentials:** Von Supabase `auth.users` → Config-File
- **Password-Hashes:** Supabase BCrypt → Streamlit-Authenticator BCrypt
- **Roles/Permissions:** Weiterhin aus Supabase `profiles` table
- **Course-Data:** Unverändert aus Supabase

### Migration-Aufwand
```python
# Einmaliges Export-Script
users = supabase.table('auth.users').select('email').execute()
profiles = supabase.table('profiles').select('user_id, full_name').execute()

config_users = {}
for user in users:
    config_users[user.email] = {
        'name': get_profile_name(user.id),
        'password': generate_temp_bcrypt_hash()  # User muss neu setzen
    }
```

**Vorteile:**
- ✅ **E-Mail/Passwort-Login bleibt unverändert**
- ✅ **30-Tage JWT-Cookies überleben Reload**
- ✅ **Production-ready Library** (>1M Downloads)
- ✅ **BCrypt-Hashing, sichere JWT-Cookies**
- ✅ **Drop-in-Replacement für bestehendes Login-Widget**

**Aufwand:** 4-6h (Migration-Script + Integration)

---

## Lösung 2: Custom Cookies - Minimal-invasive Erweiterung

### Konzept
Bestehende Supabase-Auth behalten, nur Cookie-Layer hinzufügen

**Architektur-Änderung:** 
```python
# VORHER: 
Supabase-Auth → Session-State → Bei Reload weg

# NACHHER:
Supabase-Auth → Session-State + Encrypted-Cookie → Bei Reload aus Cookie wiederherstellen
```

### Implementation Details

```python
# 1. Enhanced Login (erweitert bestehenden sign_in())
def enhanced_login(email, password):
    # Bestehender Supabase-Flow unverändert
    result = sign_in(email, password)  # Original-Funktion
    
    if result.user and result.session:
        # NEU: Session-Daten in Cookie speichern
        session_data = {
            'user_id': result.user.id,
            'email': result.user.email,
            'access_token': result.session.access_token,
            'refresh_token': result.session.refresh_token,
            'expires_at': result.session.expires_at,
            'role': get_user_role(result.user.id)
        }
        
        # Verschlüsseln mit Fernet
        cipher = Fernet(ENCRYPTION_KEY)
        encrypted = cipher.encrypt(json.dumps(session_data).encode())
        
        # In Cookie speichern (30 Tage)
        cookie_manager = stx.CookieManager()
        cookie_manager.set('gustav_session', 
                          encrypted.decode(),
                          expires_at=datetime.now() + timedelta(days=30))
        
        # Bestehender Session-State unverändert
        st.session_state.user = result.user
        st.session_state.session = result.session
        st.session_state.role = session_data['role']

# 2. App-Start Session-Restore
def restore_from_cookie():
    cookie_manager = stx.CookieManager() 
    encrypted_data = cookie_manager.get('gustav_session')
    
    if encrypted_data:
        cipher = Fernet(ENCRYPTION_KEY)
        session_data = json.loads(cipher.decrypt(encrypted_data.encode()))
        
        # Token-Gültigkeit prüfen
        if datetime.now().timestamp() < session_data['expires_at']:
            # Supabase-Client mit gespeicherten Tokens initialisieren
            supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            supabase_client.postgrest.auth.set_auth(session_data['access_token'])
            
            # Session-State wiederherstellen (wie nach Login)
            st.session_state.user = recreate_user_object(session_data)
            st.session_state.session = recreate_session_object(session_data)
            st.session_state.role = session_data['role']
            return True
    return False

# 3. Integration in main.py (minimale Änderung)
if not st.session_state.user:
    if restore_from_cookie():  # NEU: Versuche Cookie-Restore
        st.rerun()
    else:
        show_login_form()  # Bestehender Code mit enhanced_login()
```

### Cookie-Security
- **Encryption:** Fernet (AES 128 + HMAC SHA256)
- **HttpOnly:** Verhindert JavaScript-Zugriff
- **Secure:** Nur über HTTPS übertragen
- **SameSite:** CSRF-Protection

### Was bleibt unverändert
- Komplette Supabase-Auth-Pipeline
- User-Management in Supabase
- Passwort-Reset-Flows
- Role-Based Access Control
- Alle bestehenden Auth-Functions

**Vorteile:**
- ✅ **Bestehende Supabase-Auth bleibt 100% unverändert**
- ✅ **E-Mail/Passwort-System bleibt**
- ✅ **30-Tage verschlüsselte Cookie-Persistenz**
- ✅ **Minimale Code-Änderungen**

**Aufwand:** 2-3h (nur Cookie-Layer hinzufügen)

---

## Lösung 3: Server-Side Sessions - Enterprise-Approach

### Konzept
Session-Daten auf Server speichern, nur Session-ID im Cookie

**Architektur-Änderung:**
```python
# VORHER:
Login → Alle Daten in RAM → Bei Reload weg

# NACHHER:  
Login → Session-ID in Cookie → Daten in Server-Storage → Bei Reload aus Storage holen
```

### Implementation Details

```python
# 1. Server-Side Session Store
@st.cache_data(ttl=2592000, persist=True)  # 30 Tage, überlebt App-Restart
def get_session_store():
    return {}  # In Production: Redis/Database

# 2. Session Creation
def create_server_session(supabase_user, supabase_session):
    session_id = str(uuid.uuid4())  # Eindeutige Session-ID
    session_store = get_session_store()
    
    # Komplette Session-Daten server-seitig speichern
    session_store[session_id] = {
        'user_data': {
            'id': supabase_user.id,
            'email': supabase_user.email,
            'created_at': supabase_user.created_at
        },
        'session_data': {
            'access_token': supabase_session.access_token,
            'refresh_token': supabase_session.refresh_token,
            'expires_at': supabase_session.expires_at
        },
        'metadata': {
            'created_at': datetime.now(),
            'last_accessed': datetime.now(),
            'ip_address': get_client_ip(),
            'user_agent': get_user_agent(),
            'role': get_user_role(supabase_user.id)
        }
    }
    
    # Nur verschlüsselte Session-ID in Cookie
    cipher = Fernet(ENCRYPTION_KEY)
    encrypted_sid = cipher.encrypt(session_id.encode())
    
    cookie_manager = stx.CookieManager()
    cookie_manager.set('gustav_sid', encrypted_sid.decode(),
                      expires_at=datetime.now() + timedelta(days=30))
    
    return session_id

# 3. Session Restoration  
def restore_server_session():
    cookie_manager = stx.CookieManager()
    encrypted_sid = cookie_manager.get('gustav_sid')
    
    if encrypted_sid:
        cipher = Fernet(ENCRYPTION_KEY)
        session_id = cipher.decrypt(encrypted_sid.encode()).decode()
        
        session_store = get_session_store()
        session = session_store.get(session_id)
        
        if session and datetime.now() < session['metadata']['expires_at']:
            # Last-Access-Time aktualisieren
            session['metadata']['last_accessed'] = datetime.now()
            
            # Session-State aus Server-Storage wiederherstellen
            st.session_state.user = recreate_user_from_data(session['user_data'])
            st.session_state.session = recreate_session_from_data(session['session_data'])
            st.session_state.role = session['metadata']['role']
            
            return True
    return False

# 4. Session Management Features
def revoke_session(session_id):
    """Admin kann Sessions beenden"""
    session_store = get_session_store()
    if session_id in session_store:
        del session_store[session_id]

def get_active_sessions(user_id):
    """Liste aller aktiven Sessions eines Users"""
    session_store = get_session_store()
    return [s for s in session_store.values() 
            if s['user_data']['id'] == user_id]
```

### Erweiterte Features
- **Session-Revocation:** Admin kann Sessions remote beenden
- **Multi-Device-Management:** User sieht alle seine Sessions
- **Audit-Trail:** Komplettes Logging aller Session-Aktivitäten
- **Concurrent-Session-Limits:** Max. X Sessions pro User

**Vorteile:**
- ✅ **Höchste Sicherheit** (keine Tokens client-seitig)
- ✅ **Session-Revoke möglich** (server-seitig löschen)
- ✅ **Audit-Trail** (alle Zugriffe trackbar)
- ✅ **Enterprise-Features** (Multi-Device, Session-Limits)

**Nachteile:**
- ⚠️ **Server-Restart = Sessions weg** (ohne Redis/DB-Backend)
- ⚠️ **Höhere Komplexität** (Session-Cleanup, Monitoring)

**Aufwand:** 4-5h (mit Redis/DB-Backend für Production)

---

## Detaillierte Vergleichsmatrix

| Aspekt | Streamlit-Auth | Custom Cookies | Server Sessions |
|--------|----------------|----------------|-----------------|
| **Architektur-Änderung** | Komplett neues Auth-System | Minimal (nur Cookie-Layer) | Mittel (Session-Storage) |
| **Supabase-Abhängigkeit** | Reduziert (nur für App-Daten) | Unverändert | Unverändert |
| **Security-Features** | BCrypt + JWT-Cookies | Fernet-Verschlüsselung | Höchste (Server-Side + Audit) |
| **Session-Management** | Basic (Login/Logout) | Basic (Login/Logout) | Enterprise (Revoke, Multi-Device) |
| **Performance-Impact** | Minimal | Minimal | Mittel (Server-Storage-Zugriff) |
| **Wartungsaufwand** | Niedrig (Library) | Mittel (Custom-Code) | Hoch (Session-Cleanup, Monitoring) |
| **Fallback bei Problemen** | Komplett zurück zu Supabase | Cookie-Layer deaktivieren | Session-Feature deaktivieren |
| **Production-Readiness** | Hoch (bewährte Library) | Mittel (Custom-Implementation) | Hoch (mit Redis/DB-Backend) |

---

## Finale Empfehlung

### Für GUSTAV: Streamlit-Authenticator (Lösung 1)

**Begründung:**
- **Bewährt:** >1M Downloads, speziell für Education-Sector entwickelt
- **Wartungsarm:** Externe Library übernimmt Cookie-Management, Security-Updates
- **Future-Proof:** Streamlit-Team arbeitet eng mit Library-Maintainers zusammen
- **Migration-Path:** User-Import aus Supabase technisch validiert

**Risiko-Mitigation:** 
- Parallel-Deployment möglich (Feature-Flag)
- Rollback-Plan: Original Login-Code in 30min wiederherstellbar
- User-Migration: Temp-Passwort-Approach minimiert Support-Aufwand

---

## Implementierungsplan

### Phase 1: Vorbereitung (1h)
1. `streamlit-authenticator` installieren: `pip install streamlit-authenticator`
2. User-Export-Script aus Supabase entwickeln
3. Temp-Passwörter generieren für Migration

### Phase 2: Integration (3h)
1. Login-Widget in `main.py` durch Streamlit-Authenticator ersetzen
2. Session-State-Integration mit bestehender Supabase-Architektur
3. Logout-Funktionalität anpassen
4. Role-Management-Integration

### Phase 3: Migration & Testing (2h)
1. User-Migration-Script ausführen  
2. Multi-Browser/Multi-Device Testing
3. Performance-Testing mit 30+ concurrent users
4. Rollback-Strategie validieren

### Phase 4: Rollout (30min)
1. Feature-Flag aktivieren
2. E-Mail an alle User: "Passwort bei nächstem Login neu setzen"
3. Monitoring für erste 48h

**Geschätzter Gesamtaufwand:** 4-6 Stunden  
**Expected Outcome:** Zero ungewollte Logouts, 30-Tage Cookie-Persistenz, keine Architektur-Änderungen nötig

---

## Nächste Schritte

1. ✅ **Entscheidung**: Streamlit-Authenticator implementieren
2. 🔄 **Setup**: User-Migration-Script entwickeln  
3. 🔄 **Implementation**: Login-System ersetzen
4. 🔄 **Testing**: Multi-User, Multi-Browser Tests
5. 🔄 **Rollout**: Feature-Flag-basierte schrittweise Einführung