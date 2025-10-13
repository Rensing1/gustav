# Server-Proxy Storage Implementierungsplan

## Übersicht

**Problem:** Storage RLS-Policies erwarten Cookie-Authentifizierung, aber Supabase Python Client sendet nur JWT Bearer Tokens.

**Lösung:** Server-seitiger Proxy, der Uploads/Downloads durch die Anwendung leitet und dabei die korrekte Authentifizierung sicherstellt.

## Quick-Fix: Service Role Key (Implementiert)

Als temporäre Lösung wurde der Service Role Key für Storage-Uploads implementiert:

### Durchgeführte Änderungen:

1. **`/app/components/submission_input.py`** (Zeile 159-161)
   ```python
   # ALT:
   supabase = get_user_supabase_client()
   
   # NEU:
   from supabase_client import get_supabase_service_client
   supabase = get_supabase_service_client()
   
   if not supabase:
       st.error("Service-Client nicht verfügbar. Bitte Administrator kontaktieren.")
       return False
   ```

2. **`/app/components/detail_editor.py`** (2 Stellen für Material-Uploads)
   - Gleiche Änderung wie oben
   - Service Client umgeht alle RLS-Checks

### Voraussetzungen:
- `SUPABASE_SERVICE_ROLE_KEY` muss in `.env` gesetzt sein
- Container neu starten nach Änderung: `docker compose restart app`

### Sicherheitshinweise:
- ⚠️ **Umgeht ALLE Storage RLS-Checks**
- ⚠️ App validiert bereits Berechtigungen, aber keine zweite Sicherheitsebene
- ⚠️ **Dies ist eine TEMPORÄRE Lösung**

### Status: ✅ Funktioniert seit 10.09.2025

## Architektur

```
User → Streamlit App → Server-Proxy → Supabase Storage
         (Cookie)      (Service Key)    (Bypass RLS)
```

## Vorteile dieser Lösung

1. **Volle Kontrolle** über Uploads/Downloads
2. **Sicherheitsprüfungen** serverseitig möglich (Virus-Scan, Magic Numbers)
3. **Keine Architekturänderungen** - funktioniert mit bestehendem Streamlit
4. **Cookie-Auth bleibt erhalten** - konsistent mit Rest der App
5. **Monitoring & Logging** einfach integrierbar

## Implementierungsplan

### Phase 1: Storage Service erstellen

**Datei:** `/app/services/storage_proxy.py`

```python
import io
import mimetypes
from typing import Optional, BinaryIO
from supabase import Client
from app.utils.auth_integration import AuthIntegration
from app.config import get_supabase_service_client

class StorageProxy:
    """Server-seitiger Proxy für Supabase Storage Operationen"""
    
    def __init__(self):
        # Service Client umgeht RLS
        self.client: Client = get_supabase_service_client()
        self.auth = AuthIntegration()
        
    def validate_user_permissions(self, user_id: str, task_id: str, operation: str) -> bool:
        """Prüft ob User die Operation ausführen darf"""
        if operation == "upload":
            # Prüfe ob Task existiert und User zugeordnet
            result = self.client.rpc(
                "check_task_access",
                {"p_user_id": user_id, "p_task_id": task_id}
            ).execute()
            return result.data
        # Weitere Checks für download etc.
        return False
        
    def upload_file(
        self,
        file: BinaryIO,
        filename: str,
        content_type: str,
        task_id: str,
        user_id: str
    ) -> dict:
        """Upload einer Datei mit Validierung"""
        
        # 1. Berechtigungsprüfung
        if not self.validate_user_permissions(user_id, task_id, "upload"):
            raise PermissionError("Keine Berechtigung für diesen Upload")
            
        # 2. Dateivalidierung
        if content_type not in ['image/jpeg', 'image/png', 'application/pdf']:
            raise ValueError("Dateityp nicht erlaubt")
            
        # 3. Größenprüfung
        file.seek(0, 2)  # Zum Ende
        size = file.tell()
        file.seek(0)  # Zurück zum Anfang
        
        if size > 10 * 1024 * 1024:  # 10MB
            raise ValueError("Datei zu groß (max. 10MB)")
            
        # 4. Pfad generieren
        import uuid
        file_id = str(uuid.uuid4())
        ext = mimetypes.guess_extension(content_type) or '.bin'
        path = f"student_{user_id}/task_{task_id}/{file_id}{ext}"
        
        # 5. Upload via Service Client (umgeht RLS)
        try:
            result = self.client.storage.from_('submissions').upload(
                path,
                file,
                {"content-type": content_type}
            )
            
            return {
                "path": path,
                "size": size,
                "content_type": content_type
            }
        except Exception as e:
            raise Exception(f"Upload fehlgeschlagen: {str(e)}")
            
    def download_file(self, submission_id: str, user_id: str) -> tuple[BinaryIO, str, str]:
        """Download einer Datei mit Berechtigungsprüfung"""
        
        # 1. Submission-Daten holen
        result = self.client.table("submissions").select(
            "file_path, task_id, user_id, tasks(course_id)"
        ).eq("id", submission_id).single().execute()
        
        if not result.data:
            raise ValueError("Submission nicht gefunden")
            
        submission = result.data
        
        # 2. Berechtigungsprüfung
        # Student: nur eigene
        # Lehrer: alle aus eigenem Kurs
        is_teacher = self.auth.get_current_user().get("role") == "teacher"
        
        if not is_teacher and submission["user_id"] != user_id:
            raise PermissionError("Keine Berechtigung")
            
        if is_teacher:
            # Prüfe ob Lehrer Zugriff auf Kurs hat
            course_access = self.client.rpc(
                "check_course_access",
                {"p_user_id": user_id, "p_course_id": submission["tasks"]["course_id"]}
            ).execute()
            if not course_access.data:
                raise PermissionError("Kein Zugriff auf diesen Kurs")
        
        # 3. Download
        file_data = self.client.storage.from_('submissions').download(submission["file_path"])
        
        # 4. Content-Type ermitteln
        content_type = mimetypes.guess_type(submission["file_path"])[0] or 'application/octet-stream'
        
        # 5. Filename aus Pfad extrahieren
        filename = submission["file_path"].split('/')[-1]
        
        return io.BytesIO(file_data), filename, content_type
```

### Phase 2: Streamlit Integration

**Datei:** `/app/components/storage_upload_proxy.py`

```python
import streamlit as st
import io
from app.services.storage_proxy import StorageProxy
from app.utils.auth_integration import AuthIntegration

def handle_file_upload_proxy(task_id: str):
    """Streamlit Component für File Upload via Proxy"""
    
    auth = AuthIntegration()
    user = auth.get_current_user()
    
    if not user:
        st.error("Bitte anmelden")
        return
        
    uploaded_file = st.file_uploader(
        "Datei auswählen",
        type=['jpg', 'jpeg', 'png', 'pdf'],
        help="Maximal 10MB, nur JPG, PNG oder PDF"
    )
    
    if uploaded_file is not None:
        # Zeige Dateiinfo
        st.info(f"Ausgewählt: {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        
        if st.button("Datei hochladen", type="primary"):
            try:
                with st.spinner("Datei wird hochgeladen..."):
                    proxy = StorageProxy()
                    
                    # Upload via Proxy
                    result = proxy.upload_file(
                        file=uploaded_file,
                        filename=uploaded_file.name,
                        content_type=uploaded_file.type,
                        task_id=task_id,
                        user_id=user["id"]
                    )
                    
                    # Submission erstellen
                    from app.utils.db.submissions import create_submission
                    create_submission(
                        task_id=task_id,
                        content=result["path"],
                        submission_type="file"
                    )
                    
                    st.success("Datei erfolgreich hochgeladen!")
                    st.rerun()
                    
            except ValueError as e:
                st.error(f"Validierungsfehler: {e}")
            except PermissionError as e:
                st.error(f"Berechtigung verweigert: {e}")
            except Exception as e:
                st.error(f"Upload fehlgeschlagen: {e}")

def handle_file_download_proxy(submission_id: str):
    """Streamlit Component für File Download via Proxy"""
    
    auth = AuthIntegration()
    user = auth.get_current_user()
    
    if not user:
        return
        
    try:
        proxy = StorageProxy()
        file_data, filename, content_type = proxy.download_file(
            submission_id=submission_id,
            user_id=user["id"]
        )
        
        # Download Button
        st.download_button(
            label="Datei herunterladen",
            data=file_data,
            file_name=filename,
            mime=content_type
        )
        
    except Exception as e:
        st.error(f"Download fehlgeschlagen: {e}")
```

### Phase 3: Integration in bestehende Components

**Update:** `/app/components/submission_input.py`

```python
# Ersetze direkten Storage-Zugriff durch Proxy
from app.components.storage_upload_proxy import handle_file_upload_proxy

# In der render Funktion:
if submission_type == "file":
    handle_file_upload_proxy(task_id)
```

### Phase 4: Download Integration

**Update:** `/app/pages/3_Meine_Aufgaben.py`

```python
# Ersetze signed URL Generation durch Proxy
from app.components.storage_upload_proxy import handle_file_download_proxy

# Statt signed URL:
handle_file_download_proxy(submission["id"])
```

## Sicherheitsaspekte

1. **Service Key nur im Backend** - niemals an Client
2. **Berechtigungsprüfung** für jede Operation
3. **Dateivalidierung** serverseitig
4. **Größenlimits** durchgesetzt
5. **Pfad-Injection** verhindert durch UUID-Generierung

## Migration

1. Storage Proxy Service implementieren
2. Upload Components nacheinander umstellen
3. Download Components umstellen
4. Alte Storage-Client Aufrufe entfernen

## Zeitschätzung

- Storage Proxy Service: 2 Stunden
- Streamlit Components: 1 Stunde
- Integration & Testing: 2 Stunden
- **Gesamt: 5 Stunden**

## Vorteile gegenüber Pre-Signed URLs

1. Funktioniert mit bestehender Architektur
2. Keine neuen API-Endpoints nötig
3. Volle Kontrolle über Sicherheit
4. Einfacheres Error-Handling
5. Konsistente Cookie-Authentifizierung

## Nächste Schritte

1. **Kurzfristig:** Quick-Fix mit Service Role Key läuft bereits ✅
2. **Mittelfristig:** Evaluierung ob Storage-Proxy oder RLS-Anpassung
3. **Langfristig:** Einheitliche Auth-Strategie für alle Services