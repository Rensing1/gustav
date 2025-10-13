# Navigation Fix für HttpOnly Cookie Authentication

**Datum:** 2025-09-09  
**Status:** IN PROGRESS - Login behoben, Navigation-Fix ausstehend  
**Problem:** Nach Umstellung auf HttpOnly Cookies sind die Dropdown-Menüs für Kurse und Lerneinheiten leer  

## Problembeschreibung

Nach erfolgreicher Implementierung der HttpOnly Cookie Authentication (Phase 2 & 3) funktioniert die Navigation in der Streamlit-Seitenleiste nicht mehr:

- **Symptom**: Dropdown-Menüs für Kurse und Lerneinheiten bleiben leer
- **Ursache**: Streamlit kann ohne JavaScript-Zugriff auf Cookies nicht mehr direkt auf Supabase zugreifen
- **Auswirkung**: Benutzer können keine Kurse oder Lerneinheiten auswählen

## Technische Analyse

### Bisheriger Datenfluss (Legacy)
```
Streamlit → localStorage → Supabase Token → Direct DB Access
```

### Neuer Datenfluss (HttpOnly)
```
Streamlit → Cookie → Auth Service → Proxy → Supabase
```

### Kernproblem
Der Supabase Client in Streamlit hat im HttpOnly-Modus keinen gültigen Access Token, da dieser sicher im Cookie gespeichert ist und nicht via JavaScript ausgelesen werden kann.

## Lösungsansatz: Session-Proxy ohne Service Role Key

Statt einen Service Role Key zu verwenden (Sicherheitsrisiko), implementieren wir API-Proxy-Endpunkte im Auth Service, die:
1. Die Session aus dem Cookie validieren
2. Den originalen User-Token aus der Session extrahieren
3. Mit diesem Token authentifizierte Supabase-Anfragen stellen

## Implementierungsschritte

### 1. Data Proxy Endpunkte ✅
**Datei**: `auth_service/app/routes/data_proxy.py`
- `/auth/api/courses` - Kursliste für User
- `/auth/api/courses/{id}/units` - Lerneinheiten pro Kurs
- `/auth/api/user/progress` - Lernfortschritt
- `/auth/api/user/profile` - Benutzerprofil

### 2. Session-Token Wiederverwendung ✅
**Datei**: `auth_service/app/services/supabase_auth_proxy.py`
- Extrahiert Original Access/Refresh Tokens aus Session
- Erstellt authentifizierten Supabase Client
- Client-Caching für Performance

### 3. DataFetcher für Streamlit ✅
**Datei**: `app/utils/data_fetcher.py`
- Erkennt HttpOnly-Modus automatisch
- Leitet Requests an Auth Service Proxy
- Synchrone API (kein async)

### 4. Cookie Utils ✅
**Datei**: `app/utils/cookie_utils.py`
- Einheitlicher Cookie-Zugriff
- Unterstützt `st.context.cookies` und Header-Parsing
- Debug-Logging

### 5. CacheManager Anpassung ✅
**Datei**: `app/utils/cache_manager.py`
- Nutzt DataFetcher statt direkten Supabase-Zugriff
- Behält Cache-Strategie (90min Kurse, 10min Units)

## Login-Problem: Gelöst ✅

### Fehlermeldung (behoben)
```
session_create_failed code=P0001 error='Failed to create session'
```

### Ursache
Der Login schlug fehl, weil der Auth Service Container nach Code-Änderungen nicht neu gebaut wurde:
- `docker compose restart` lädt nur den bestehenden Container neu
- `docker compose build && docker compose up -d` erstellt das Image mit dem neuen Code

### Lösung
```bash
# Korrekt - baut Container mit neuem Code:
docker compose build auth app && docker compose up auth app -d

# Falsch - lädt nur alten Container neu:
docker compose restart app
```

### Wichtige Erkenntnis
Die `CLAUDE.md` Dokumentation muss aktualisiert werden - der Befehl `docker compose restart app` aktiviert KEINE Code-Änderungen!

## Aktuelles Problem: Navigation-Dropdowns leer

Nach erfolgreichem Login funktioniert die Navigation immer noch nicht:

### Vermutete Ursachen

1. **Session-Token nicht im Auth-Proxy verfügbar**
   - Tokens werden beim Login gespeichert
   - Aber beim Abrufen über den Proxy nicht gefunden
   - Debug-Logs müssen aktiviert werden

2. **Datentyp-Serialisierung**
   - Das `data` Field könnte als JSON-String statt Dict gespeichert werden
   - PostgreSQL JSONB vs. String-Konvertierung

## Nächste Schritte

1. **Session-Daten-Struktur verifizieren**:
   - Logging in `data_proxy.py` hinzugefügt
   - Prüfen welche Keys in session_data vorhanden sind
   - Typ des `data` Fields untersuchen

2. **SupabaseAuthProxy Debug-Logs**:
   - Detaillierte Logs für Token-Extraktion
   - JSON-Parsing verifizieren

3. **Alternative: Token direkt speichern**:
   - Statt in `data` Field könnte man access_token direkt speichern
   - Aber: Würde Session-Struktur ändern

## Lessons Learned

1. **Cookie-Zugriff in Streamlit**: Verschiedene Methoden je nach Version
2. **Zirkuläre Imports vermeiden**: DataFetcher Import nur bei Bedarf
3. **Legacy-Code entfernen**: Vereinfacht Debugging erheblich
4. **Ausführliches Logging**: Essentiell für verteilte Systeme

## Offene Fragen

1. Warum werden die Debug-Logs von SupabaseAuthProxy nicht angezeigt?
2. Ist die Session-Daten-Struktur zwischen Create und Get konsistent?
3. Sollten wir die Token-Speicherung vereinfachen?

## Update 2025-09-08

### Login-Fix durchgeführt
- Problem: Auth Service Container verwendete alten Code
- Lösung: `docker compose build auth app && docker compose up auth app -d`
- Status: Login funktioniert wieder für alle Benutzer

### Navigation weiterhin defekt
- Dropdowns bleiben leer trotz funktionierendem Login
- Nächster Schritt: Debug-Logs aktivieren und Session-Token-Flow überprüfen

## Ursachenanalyse Navigation-Problem (2025-09-08)

### Root Cause identifiziert

Es existieren zwei separate Login-Flows mit unterschiedlicher Token-Behandlung:

1. **API-Login** (`/api/login` in `routes/auth.py`):
   - Speichert korrekt Session-Tokens in der Datenbank
   - Wird aber NICHT von der UI verwendet

2. **Web-Login** (`/login` in `pages/login.py`):
   - Wird tatsächlich von der UI verwendet
   - Speichert KEINE Tokens in der Session ❌
   - Ruft `create_session()` ohne Token-Parameter auf

### Beweise

1. **Session-Erstellung ohne Tokens**:
   ```
   create_session_params data_keys=[] data_type=<class 'NoneType'>
   ```

2. **Datenbank-Inhalt**:
   ```sql
   SELECT session_id, user_email, data FROM auth_sessions;
   -- Ergebnis: data = {} (leer!)
   ```

3. **Navigation-Fehler**:
   ```
   no_access_token_in_session session_info_keys=[]
   ```

### Technischer Ablauf

```
User Login (Web) → pages/login.py → authenticate_user()
    ↓
Supabase Auth (Tokens werden generiert)
    ↓  
authenticate_user gibt NUR {id, email, role} zurück ❌
    ↓
create_session() wird OHNE Token-Daten aufgerufen
    ↓
Session in DB: data = {} (leer!)
    ↓
Navigation-Proxy findet keine Tokens → Fehler
```

## Lösungsplan

### Option 1: Quick Fix (Empfohlen für Sofortmaßnahme) ✅

**Zeitaufwand**: 30-60 Minuten
**Risiko**: Minimal
**Dateien**: 2 (routes/login.py, pages/login.py)

#### Implementierung:

1. **routes/login.py** - `authenticate_user()` erweitern:
   ```python
   return {
       "id": user.id,
       "email": user.email,
       "role": profile.get("role", "student"),
       # NEU: Session-Tokens hinzufügen
       "access_token": session.access_token,
       "refresh_token": session.refresh_token,
       "expires_at": session.expires_at
   }
   ```

2. **pages/login.py** - Session-Erstellung anpassen:
   ```python
   session_id = await session_store.create_session(
       user_id=user_data["id"],
       user_email=user_data["email"],
       user_role=user_data.get("role", "user"),
       # NEU: Token-Daten hinzufügen
       data={
           "access_token": user_data.get("access_token"),
           "refresh_token": user_data.get("refresh_token"),
           "expires_at": user_data.get("expires_at")
       } if user_data.get("access_token") else None
   )
   ```

#### Sicherheitsanalyse:
- ✅ Keine neuen Sicherheitsrisiken
- ✅ Tokens bleiben im geschützten Backend
- ✅ Bestehende Security-Mechanismen intakt

#### Wartbarkeit:
- ⚠️ Zwei Login-Flows bleiben inkonsistent
- ⚠️ Technische Schuld wird nicht abgebaut
- ✅ Einfaches Rollback möglich
- ✅ Keine Breaking Changes

### Option 2: Unified Login Flow (Langfristige Lösung)

**Zeitaufwand**: 7-10 Stunden
**Risiko**: Mittel
**Dateien**: 6-8

#### Vorteile:
- Konsistente Login-Logik
- Bessere Wartbarkeit
- Einfachere Tests
- Vorbereitet für OAuth/2FA

#### Implementierungsplan:
1. Zentrale `AuthService` Klasse erstellen
2. Beide Login-Routes refactoren
3. Gemeinsames Error-Handling
4. Umfassende Tests schreiben
5. Schrittweise Migration

## Empfehlung

1. **Sofort**: Option 1 implementieren
   - Navigation wird wieder funktionsfähig
   - Benutzer können weiterarbeiten
   - Minimales Risiko

2. **Innerhalb 2-4 Wochen**: Option 2 planen und umsetzen
   - Technische Schuld abbauen
   - Zukunftssicher machen
   - Mit ausreichend Tests

## Wichtige Erkenntnisse

1. **Docker-Befehle**: 
   - `docker compose restart` lädt nur Container neu (alter Code!)
   - `docker compose build` erstellt neues Image (neuer Code!)
   - CLAUDE.md muss aktualisiert werden

2. **Zwei Login-Systeme**:
   - Historisch gewachsen (API zuerst, dann Web-UI)
   - Unterschiedliche Anforderungen (JSON vs. HTML)
   - Führt zu Inkonsistenzen

3. **Session-Design**:
   - Benötigt Tokens für Proxy-Funktionalität
   - JSONB-Feld flexibel aber fehleranfällig
   - Klare Dokumentation essentiell

## Status Quick Fix (2025-09-08)

### ✅ Erfolgreich implementiert:
1. **Login funktioniert** - Tokens werden in Session gespeichert
2. **Navigation-Dropdowns** - Kurse werden angezeigt
3. **Tabellennamen korrigiert** - `learning_units` → `learning_unit`
4. **Query-Fix für Lerneinheiten** - Join über `course_learning_unit_assignment`

### ❌ Neue Probleme identifiziert:

#### Problem 1: Direkte DB-Queries schlagen fehl
**Ursache**: `session_client.py` überspringt Token-Auth im HttpOnly-Mode:
```python
if access_token == 'managed-by-cookies':
    pass  # Keine Authentifizierung!
```

**Betroffene Seiten**:
- `pages/1_Kurse.py`
- `pages/2_Lerneinheiten.py`
- Alle Seiten die `get_user_supabase_client()` verwenden

#### Problem 2: Fehlermeldung in 2_Lerneinheiten.py
```
JSON object requested, multiple (or no) rows returned
The result contains 0 rows
```
**Ursache**: `get_learning_unit_by_id()` findet keine Einheit mit der gegebenen ID

## Lösungsplan: DataFetcher-Erweiterung (Option A)

### Phase 1: DataFetcher API erweitern
1. **Neue Endpunkte im Auth Service**:
   - `/auth/api/learning-units` - Alle Lerneinheiten des Lehrers
   - `/auth/api/learning-units/{id}` - Einzelne Lerneinheit
   - `/auth/api/courses/{id}/assigned-units` - Zugewiesene Einheiten
   - `/auth/api/learning-units/create` - Neue Einheit erstellen
   - `/auth/api/sections/{unit_id}` - Sections einer Unit
   - `/auth/api/courses/create` - Neuen Kurs erstellen
   - `/auth/api/courses/{id}/students` - Schüler eines Kurses
   - `/auth/api/courses/{id}/assignments` - Unit-Zuweisungen

2. **DataFetcher erweitern** mit entsprechenden Methoden

### Phase 2: DB-Queries Migration
1. **Wrapper-Funktionen** in `db_queries.py`:
   - Prüfen ob HttpOnly-Mode aktiv
   - Falls ja: DataFetcher verwenden
   - Falls nein: Legacy direkter Zugriff

2. **Schrittweise Migration**:
   - Kritische Funktionen zuerst
   - Tests für beide Modi
   - Fallback-Mechanismen

### Phase 3: Cleanup
1. Legacy-Code entfernen
2. Session-Client vereinfachen
3. Dokumentation aktualisieren

### Zeitplan:
- Phase 1: 4-5 Stunden
- Phase 2: 3-4 Stunden  
- Phase 3: 1-2 Stunden
- **Gesamt: 8-11 Stunden**

### Nächste Schritte:
1. DataFetcher-Endpunkte implementieren
2. DB-Query-Wrapper erstellen
3. Betroffene Seiten testen
4. Schrittweise Migration