# Wartungsmodus-Implementierung

## 2025-09-03T11:20:00+02:00

**Ziel:** Temporäre Wartungsmodus-Funktion implementieren, die während Code-Änderungen ein Baustellenschild/Wartungshinweis anzeigt.

**Annahmen:** 
- Wartungsmodus soll manuell aktivierbar sein (kein automatischer Trigger)
- Benutzer sollen informative Nachricht sehen statt normale App-Funktionen
- Administratoren/Lehrer können optional weiterhin Zugriff haben
- Wartungsmodus sollte schnell aktiviert/deaktiviert werden können

**Offene Punkte:**
1. Trigger-Mechanismus: ENV-Variable, Admin-UI oder Datei-Flag?
2. Zugriffs-Granularität: Alle Nutzer oder nur bestimmte Rollen sperren?
3. Wartungsnachricht: Statischer Text oder konfigurierbare Nachricht?
4. API-Verhalten: Blockierung oder Wartungsstatus-Response?
5. Deployment-Integration: In docker-compose restart Workflow integriert?

---

## Implementierungsansätze (3 Alternativen)

### Ansatz A: Environment Variable (⭐ Empfohlen)
**Vorteile:** Saubere Integration, Docker-native, konfigurierbar
**Nachteile:** Erfordert Container-Neustart

**Code-Änderungen:**

1. **`app/config.py` erweitern:**
```python
# Wartungsmodus
MAINTENANCE_MODE: bool = os.environ.get("MAINTENANCE_MODE", "false").lower() == "true"
MAINTENANCE_MESSAGE: str = os.environ.get("MAINTENANCE_MESSAGE", "🚧 Wartungsarbeiten - Bitte versuchen Sie es später erneut")
```

2. **`app/main.py` Wartungsprüfung (vor Zeile 58):**
```python
from config import MAINTENANCE_MODE, MAINTENANCE_MESSAGE

# Wartungsmodus prüfung (vor allen anderen UI-Elementen)
if MAINTENANCE_MODE:
    st.set_page_config(page_title="Wartung - GUSTAV", page_icon="🚧")
    st.error("🚧 **Wartungsmodus aktiv**")
    st.info(MAINTENANCE_MESSAGE)
    st.markdown("---")
    st.markdown("**Für Administratoren:** Deaktivieren Sie MAINTENANCE_MODE in der .env-Datei")
    st.stop()
```

3. **`docker-compose.yml` Environment erweitern:**
```yaml
app:
  environment:
    - MAINTENANCE_MODE=${MAINTENANCE_MODE:-false}
    - MAINTENANCE_MESSAGE=${MAINTENANCE_MESSAGE:-🚧 Wartungsarbeiten in Bearbeitung}
```

4. **`.env` erweitern:**
```bash
# Wartungsmodus
MAINTENANCE_MODE=false
MAINTENANCE_MESSAGE="🚧 Wartungsarbeiten - Die Plattform ist vorübergehend nicht verfügbar"
```

**Aktivierung/Deaktivierung:**
```bash
# Aktivieren
echo "MAINTENANCE_MODE=true" >> .env
docker compose restart app

# Deaktivieren  
sed -i 's/MAINTENANCE_MODE=true/MAINTENANCE_MODE=false/' .env
docker compose restart app
```

---

### Ansatz B: nginx-basiert
**Vorteile:** Sofortige Aktivierung, kein App-Restart nötig
**Nachteile:** Zusätzliche nginx-Konfiguration, weniger flexibel

**Code-Änderungen:**

1. **`nginx/maintenance.html` (neue Datei):**
```html
<!DOCTYPE html>
<html>
<head>
    <title>🚧 GUSTAV - Wartungsmodus</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial; text-align: center; margin: 100px; }
        .maintenance { color: #ff6b6b; font-size: 24px; }
        .message { color: #666; font-size: 18px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="maintenance">🚧 Wartungsmodus aktiv</div>
    <div class="message">Die GUSTAV-Plattform wird gerade gewartet.<br>Bitte versuchen Sie es in wenigen Minuten erneut.</div>
</body>
</html>
```

2. **`nginx/default.conf` erweitern:**
```nginx
# Wartungsmodus-Check (vor location /)
location @maintenance {
    root /var/www;
    try_files /maintenance.html =503;
}

location / {
    # Prüfe auf Wartungsdatei
    if (-f /var/www/maintenance.flag) {
        return 503;
    }
    
    proxy_pass http://app:8501;
    # ... bestehende Proxy-Konfiguration
}

error_page 503 @maintenance;
```

3. **`maintenance-toggle.sh` (neue Datei):**
```bash
#!/bin/bash
MAINTENANCE_FLAG="/path/to/nginx/www/maintenance.flag"

case "$1" in
  enable)
    touch "$MAINTENANCE_FLAG"
    echo "Wartungsmodus aktiviert"
    ;;
  disable)
    rm -f "$MAINTENANCE_FLAG"
    echo "Wartungsmodus deaktiviert"
    ;;
  *)
    echo "Usage: $0 {enable|disable}"
    exit 1
    ;;
esac
```

---

### Ansatz C: Datei-Flag (Ohne Container-Restart)
**Vorteile:** Schnelle Aktivierung, kein Restart nötig
**Nachteile:** Datei-basiert, weniger robust

**Code-Änderungen:**

1. **`app/main.py` Datei-Check (vor Zeile 58):**
```python
import os.path
from pathlib import Path

MAINTENANCE_FILE = Path("/app/maintenance.flag")

# Wartungsmodus über Datei-Flag
if MAINTENANCE_FILE.exists():
    try:
        maintenance_message = MAINTENANCE_FILE.read_text().strip() or "🚧 Wartungsarbeiten in Bearbeitung"
    except:
        maintenance_message = "🚧 Wartungsarbeiten in Bearbeitung"
    
    st.set_page_config(page_title="Wartung - GUSTAV", page_icon="🚧")
    st.error("🚧 **Wartungsmodus aktiv**")
    st.info(maintenance_message)
    st.markdown("---")
    st.markdown("**Für Administratoren:** Löschen Sie `/app/maintenance.flag` zum Deaktivieren")
    st.stop()
```

2. **Toggle-Commands:**
```bash
# Aktivieren mit Nachricht
echo "🚧 Geplante Wartungsarbeiten - Dauer ca. 30 Minuten" > app/maintenance.flag

# Aktivieren ohne Nachricht
touch app/maintenance.flag

# Deaktivieren
rm app/maintenance.flag
```

---

## Security/Privacy Überlegungen

- **Keine sensiblen Daten** in Wartungsnachrichten
- **Kein Admin-Bypass** über URL-Parameter (Sicherheitsrisiko)
- **Logging** von Wartungsmodus-Aktivierungen
- **Graceful Degradation** für laufende Sessions

---

## Migration/Testing Plan

**Happy Path Tests:**
1. Wartungsmodus aktivieren → Wartungsseite wird angezeigt
2. Benutzer-Sessions bleiben isoliert
3. Wartungsmodus deaktivieren → Normale App-Funktion
4. Konfigurierbare Nachrichten funktionieren

**Negative Tests:**
1. Ungültige MAINTENANCE_MODE Werte → Fallback auf false
2. Wartungsmodus lässt sich nicht deaktivieren → Container-Restart als Fallback
3. Maintenance-Flag-Datei nicht löschbar → Datei-Permissions prüfen

**Rollback-Strategie:**
- ENV-Variable: `MAINTENANCE_MODE=false` + Container-Restart
- nginx: Maintenance-Flag löschen
- Datei-Flag: maintenance.flag löschen

---

## Beschluss
**Noch ausstehend** - Awaiting user decision on preferred approach

**Nächster Schritt:** 
Entscheidung für Ansatz A/B/C + Implementierung des gewählten Ansatzes

---

## Implementierungslog
*Hier werden Fortschritte und Erkenntnisse während der Umsetzung dokumentiert*