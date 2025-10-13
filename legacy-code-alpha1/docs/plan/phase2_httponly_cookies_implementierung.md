# Phase 2: HttpOnly Cookies Session Management - Implementierungsplan

**Datum:** 2025-01-09  
**Status:** PLANUNG  
**Priorität:** KRITISCH (Security-Fix nach LocalStorage-Rollback)  
**Geschätzte Dauer:** 1-2 Wochen

## Executive Summary

Nach dem kritischen Session-Bleeding-Vorfall mit LocalStorage ist die Implementierung einer robusten, sicheren Session-Management-Lösung zwingend erforderlich. HttpOnly Cookies mit einem dedizierten Auth-Service ist die einzige technisch saubere Lösung, die vollständige Session-Isolation zwischen verschiedenen Browsern garantiert.

## Problem-Statement

### Aktuelle Situation (nach Rollback)
- **F5-Logout-Problem:** Nutzer verlieren ihre Session bei jedem Page-Reload
- **UX-Impact:** 30+ tägliche Nutzer-Beschwerden
- **Technische Schuld:** Streamlit Session-State ist RAM-basiert und nicht persistent

### LocalStorage-Probleme (dokumentiert)
- **Session-Bleeding:** LocalStorage ist domain-global zwischen allen Browsern
- **Security-Risiko:** DSGVO-kritische Verletzung der Nutzer-Isolation
- **Nicht behebbar:** Fundamentales Browser-API-Verhalten

## Lösung: HttpOnly Cookie Architecture

### Warum HttpOnly Cookies?

| Feature | LocalStorage | HttpOnly Cookies |
|---------|--------------|------------------|
| Browser-Isolation | ❌ Domain-global | ✅ Browser-spezifisch |
| XSS-Schutz | ❌ JS-zugänglich | ✅ JS-immun |
| Session-Management | ❌ Client-seitig | ✅ Server-seitig |
| OWASP-Konformität | ❌ Explizit abgeraten | ✅ Best Practice |
| Multi-Tab-Support | ⚠️ Problematisch | ✅ Native Unterstützung |

## Technische Architektur

### Komponenten-Übersicht

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────┐
│   Browser   │────▶│    nginx     │────▶│  FastAPI    │────▶│ Supabase │
│             │◀────│ (auth_request)│◀────│Auth Service │◀────│    DB    │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────┘
     Cookie              Proxy                Session            Storage
```

### 1. FastAPI Auth Service (`/auth-service`)

```python
# auth_service/main.py
from fastapi import FastAPI, Response, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
from datetime import datetime, timedelta
import secrets
import redis
from typing import Optional

app = FastAPI()
redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)
security = HTTPBearer()

# Session configuration
SESSION_COOKIE_NAME = "gustav_session_id"
SESSION_DURATION = timedelta(minutes=90)  # Unterrichtsstunde
COOKIE_DOMAIN = ".gustav.app"  # oder localhost für dev

@app.post("/auth/login")
async def login(email: str, password: str, response: Response):
    """Handle user login and create session."""
    # Validate with Supabase
    supabase_response = await validate_supabase_login(email, password)
    if not supabase_response.valid:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create session
    session_id = secrets.token_urlsafe(32)
    session_data = {
        "user_id": supabase_response.user.id,
        "email": supabase_response.user.email,
        "role": get_user_role(supabase_response.user.id),
        "supabase_access_token": supabase_response.session.access_token,
        "supabase_refresh_token": supabase_response.session.refresh_token,
        "created_at": datetime.utcnow().isoformat(),
        "last_activity": datetime.utcnow().isoformat()
    }
    
    # Store in Redis with TTL
    redis_client.setex(
        f"session:{session_id}",
        int(SESSION_DURATION.total_seconds()),
        json.dumps(session_data)
    )
    
    # Set HttpOnly cookie
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=True,  # HTTPS only
        samesite="strict",
        domain=COOKIE_DOMAIN,
        max_age=int(SESSION_DURATION.total_seconds())
    )
    
    return {"status": "success", "user_id": supabase_response.user.id}

@app.get("/auth/validate")
async def validate_session(session_id: str = Depends(get_session_from_cookie)):
    """Validate session for nginx auth_request."""
    session_data = redis_client.get(f"session:{session_id}")
    if not session_data:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    # Update last activity
    session = json.loads(session_data)
    session["last_activity"] = datetime.utcnow().isoformat()
    redis_client.setex(
        f"session:{session_id}",
        int(SESSION_DURATION.total_seconds()),
        json.dumps(session)
    )
    
    # Set headers for nginx
    return Response(
        status_code=200,
        headers={
            "X-User-Id": session["user_id"],
            "X-User-Email": session["email"],
            "X-User-Role": session["role"]
        }
    )

@app.post("/auth/logout")
async def logout(response: Response, session_id: str = Depends(get_session_from_cookie)):
    """Logout user and clear session."""
    redis_client.delete(f"session:{session_id}")
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        domain=COOKIE_DOMAIN
    )
    return {"status": "logged out"}
```

### 2. nginx Configuration Update

```nginx
# nginx/default.conf additions
location = /auth/validate {
    internal;
    proxy_pass http://auth-service:8001/auth/validate;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
    proxy_set_header X-Original-URI $request_uri;
}

location / {
    # Validate every request
    auth_request /auth/validate;
    auth_request_set $user_id $upstream_http_x_user_id;
    auth_request_set $user_email $upstream_http_x_user_email;
    auth_request_set $user_role $upstream_http_x_user_role;
    
    # Pass user info to Streamlit
    proxy_set_header X-User-Id $user_id;
    proxy_set_header X-User-Email $user_email;
    proxy_set_header X-User-Role $user_role;
    
    proxy_pass http://app:8501;
}

location /auth/ {
    proxy_pass http://auth-service:8001/auth/;
}
```

### 3. Streamlit Integration

```python
# app/utils/auth_headers.py
import streamlit as st
from typing import Optional, Dict

def get_user_from_headers() -> Optional[Dict]:
    """Extract user info from nginx headers."""
    headers = st.context.headers if hasattr(st.context, 'headers') else {}
    
    user_id = headers.get('X-User-Id')
    if not user_id:
        return None
    
    return {
        'id': user_id,
        'email': headers.get('X-User-Email'),
        'role': headers.get('X-User-Role')
    }

# app/main.py updates
from utils.auth_headers import get_user_from_headers

# Replace session check with header check
user_info = get_user_from_headers()
if user_info:
    st.session_state.user = user_info
    st.session_state.role = user_info['role']
else:
    # Redirect to login
    st.markdown("""
    <script>
    window.location.href = '/auth/login';
    </script>
    """, unsafe_allow_html=True)
```

### 4. Redis Session Store

```yaml
# docker-compose.yml additions
redis:
  image: redis:7-alpine
  container_name: gustav_redis
  volumes:
    - redis_data:/data
  networks:
    - gustav-network
  command: redis-server --appendonly yes

volumes:
  redis_data:
```

## Implementation Phases

### Phase 2.1: Auth Service Foundation (2-3 Tage)
1. FastAPI Auth Service Setup
   - [ ] Projekt-Struktur `/auth-service`
   - [ ] FastAPI mit Redis-Integration
   - [ ] Supabase Auth-Wrapper
   - [ ] Session-Management-Endpoints

2. Docker Integration
   - [ ] Auth Service Dockerfile
   - [ ] Redis Container
   - [ ] docker-compose Updates

### Phase 2.2: nginx Integration (2-3 Tage)
1. nginx auth_request Module
   - [ ] auth_request Direktive
   - [ ] Header-Forwarding
   - [ ] Error-Page-Handling

2. Routing Configuration
   - [ ] `/auth/*` Routes zu Auth Service
   - [ ] Protected Routes mit Validation
   - [ ] Static Assets Bypass

### Phase 2.3: Streamlit Migration (3-4 Tage)
1. Header-basierte Authentication
   - [ ] Header-Parsing-Utilities
   - [ ] Session-State-Migration
   - [ ] Logout-Handling

2. Login/Logout Flow
   - [ ] Login-Page als separates HTML
   - [ ] Redirect-Logic
   - [ ] Error-Handling

### Phase 2.4: Testing & Rollout (2-3 Tage)
1. Comprehensive Testing
   - [ ] Unit-Tests für Auth Service
   - [ ] Integration-Tests
   - [ ] Multi-Browser-Tests
   - [ ] Performance-Tests

2. Staged Rollout
   - [ ] Feature-Flag-System
   - [ ] Canary Deployment
   - [ ] Monitoring Setup

## Security Considerations

### Cookie Security
```python
response.set_cookie(
    key=SESSION_COOKIE_NAME,
    value=session_id,
    httponly=True,      # XSS-Schutz
    secure=True,        # HTTPS only
    samesite="strict",  # CSRF-Schutz
    domain=COOKIE_DOMAIN,
    max_age=SESSION_TTL
)
```

### Session Security
- Redis-basierte Sessions mit TTL
- Automatisches Session-Timeout nach Inaktivität
- Session-Invalidierung bei Logout
- IP-Binding optional möglich

### Defense in Depth
1. **nginx Layer:** Request-Validation für jeden Request
2. **Auth Service:** Session-Management und Token-Refresh
3. **Redis:** In-Memory Session Store mit Persistence
4. **Streamlit:** Read-only Header-Access

## Migration Strategy

### Zero-Downtime Migration
1. **Parallel Development:** Auth Service entwickeln ohne bestehenden Code zu ändern
2. **Feature Flag:** Schrittweise Aktivierung für Test-User
3. **Gradual Rollout:** 10% → 50% → 100% der User
4. **Rollback Plan:** nginx Config-Switch für sofortigen Rollback

### Data Migration
- Keine Datenmigration erforderlich
- Sessions werden neu erstellt
- User müssen sich einmalig neu anmelden

## Success Metrics

### Technical Metrics
- [ ] Session-Bleeding: 0 Vorfälle
- [ ] F5-Logout-Rate: <1%
- [ ] Session-Creation: <500ms
- [ ] Auth-Validation: <50ms per Request

### User Metrics
- [ ] Login-Success-Rate: >95%
- [ ] User-Beschwerden: -90%
- [ ] Session-Duration: 90min (Unterrichtsstunde)

## Risk Assessment

### Identified Risks
1. **Performance:** Additional auth_request overhead
   - Mitigation: Redis-Caching, Connection-Pooling
   
2. **Complexity:** Neue Komponente im Stack
   - Mitigation: Comprehensive Documentation, Monitoring

3. **nginx Dependency:** auth_request Module erforderlich
   - Mitigation: Standard in nginx enthalten

## Timeline

**Gesamt: 9-13 Arbeitstage**

Woche 1:
- Tag 1-3: Auth Service Development
- Tag 4-6: nginx Integration

Woche 2:
- Tag 7-9: Streamlit Migration
- Tag 10-11: Testing
- Tag 12-13: Rollout

## Nächste Schritte

1. **Sofort:** Review dieses Plans mit Team
2. **Tag 1:** Auth Service Projekt-Setup
3. **Parallel:** nginx auth_request Tests in Dev-Environment

---

## Appendix: Alternative Ansätze (verworfen)

### JWT in Cookie
- Pro: Kein Redis nötig
- Contra: Größere Cookies, keine Revocation

### Session in PostgreSQL
- Pro: Keine neue Dependency
- Contra: Performance, keine TTL

### Proxy-Auth (OAuth2-Proxy)
- Pro: Standard-Lösung
- Contra: Overhead, externe Dependency