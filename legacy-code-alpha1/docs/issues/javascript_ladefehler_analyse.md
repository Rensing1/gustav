# JavaScript-Ladefehler Analyse: TypeError "Failed to fetch dynamically imported module"

**Datum:** 2025-09-02T15:59:00+02:00  
**Problem:** `TypeError: Failed to fetch dynamically imported module: https://gymalf-gustav.duckdns.org/static/js/index.CFRGZDz1.js`  
**Status:** Kritisch - betrifft Hauptseite der Anwendung  

## 1. Problemanalyse

### 1.1 Identifiziertes Kernproblem
Das Problem liegt **nicht** in fehlenden nginx-Konfigurationen für statische Assets, sondern in einem **Asset-Version-Mismatch** zwischen dem Streamlit-Container und den gecachten Browser-Referenzen.

**Entscheidende Erkenntnisse:**
- Die Datei `index.CFRGZDz1.js` existiert **nicht** im Streamlit-Container
- Stattdessen ist `index.CD8HuT3N.js` vorhanden (7,1 MB JavaScript-Modul)  
- Nginx liefert korrekterweise einen 200-Status für `/static/js/index.CFRGZDz1.js`
- Der Inhalt ist jedoch HTML (1.522 Bytes) statt JavaScript - nginx gibt die Streamlit-Index-Seite zurück

### 1.2 Detaillierte Ursachenanalyse

**Browser-Perspektive:**
```javascript
// Browser versucht dynamischen Import
import('./static/js/index.CFRGZDz1.js')
// Erhält HTML statt JavaScript → TypeError
```

**Nginx-Verhalten:**
- Request: `GET /static/js/index.CFRGZDz1.js` → HTTP 200 (aber HTML-Content)
- Korrekte Assets wie `index.CD8HuT3N.js` → HTTP 304/200 mit JS-Content

**Root Cause:**
1. **Container-Restart ohne Browser-Cache-Clear:** Nach einem Streamlit-Update/Restart wurden die Asset-Hashes neu generiert
2. **Nginx Fallback-Regel:** Nicht existierende `/static/js/*` Pfade werden an Streamlit weitergeleitet, das die Index-HTML zurückgibt
3. **Browser-Cache-Persistence:** Browser hält an alten Asset-Referenzen fest

### 1.3 Betroffene Komponenten
- **Primär:** Streamlit Frontend-Bootstrapping
- **Sekundär:** Dynamische ES6-Module (Code-Splitting)
- **Infrastruktur:** Nginx Proxy, Browser-Caching, Container-Lifecycle

## 2. Lösungsvorschläge

### 2.1 Sofortmaßnahme (Quickfix)
**Ziel:** Problem innerhalb von 5 Minuten beheben

```bash
# Streamlit Container Neustart erzwingen
docker compose restart app

# Browser-Cache der betroffenen Nutzer clearen lassen
# (Client-seitiger Hard-Refresh: Strg+F5 / Cmd+Shift+R)
```

**Risiko:** Nutzer müssen manuell Browser-Cache leeren

### 2.2 Robuste Lösung (Nginx-Konfiguration)
**Ziel:** Strukturelle Lösung für Asset-Handling

**Problem identifiziert in nginx/default.conf:53-75:**
```nginx
# Aktuell: Alle Requests gehen an Streamlit
location / {
    proxy_pass http://app:8501;
    # ... 
}
```

**Lösungsansatz: Spezifische Asset-Routen**
```nginx
# Neue Konfiguration vor location /
location ~* ^/static/js/.*\.js$ {
    proxy_pass http://app:8501;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # Asset-spezifische Header
    add_header Cache-Control "public, max-age=31536000, immutable";
    add_header Vary "Accept-Encoding";
    
    # Fehlerbehandlung für nicht-existierende Assets
    proxy_intercept_errors on;
    error_page 404 = @asset_fallback;
}

location @asset_fallback {
    # Fallback für veraltete Asset-Referenzen
    return 410 "Asset not found - please clear browser cache";
    add_header Content-Type text/plain;
}

# Standard-Route (bleibt unverändert)
location / {
    proxy_pass http://app:8501;
    # ... bestehende Konfiguration
}
```

### 2.3 Präventive Maßnahmen
**Ziel:** Künftige Asset-Version-Konflikte vermeiden

#### Cache-Invalidierung bei Deployment
```bash
# In deployment Pipeline
echo "Deployment $(date): Container-Restart mit Cache-Purge"
docker compose restart app
# Optional: Cache-Header für Browser
curl -H "Cache-Control: no-cache" https://gymalf-gustav.duckdns.org/
```

#### Container Health Checks erweitern
```yaml
# docker-compose.yml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8501/static/css/index.C8X8rNzw.css"]
  interval: 30s
  timeout: 10s
  retries: 3
```

#### Asset-Version-Monitoring
```bash
# Überwachungsscript
#!/bin/bash
CURRENT_ASSETS=$(docker exec gustav_app find /usr/local/lib/python3.10/site-packages/streamlit/static/static/js/ -name "index.*.js" | basename)
echo "$(date): Current main asset: $CURRENT_ASSETS" >> /var/log/asset-versions.log
```

## 3. Implementierungsplan

### Phase 1: Sofortmaßnahme (heute)
1. ✅ Problem identifiziert und analysiert
2. 🔄 Container-Restart durchführen
3. 📋 Nutzer über Browser-Cache-Clear informieren

### Phase 2: Nginx-Optimierung (diese Woche)
1. 📝 Nginx-Konfiguration erweitern (asset-spezifische Routen)
2. 🧪 Lokales Testing der neuen Konfiguration  
3. 🚀 Deployment mit Rollback-Plan
4. ✅ Verification mit verschiedenen Browsern

### Phase 3: Monitoring & Prävention (nächste Woche)  
1. 📊 Asset-Version-Monitoring implementieren
2. 🔧 Deployment-Pipeline um Cache-Invalidierung erweitern
3. 📖 Runbook für ähnliche Probleme dokumentieren

## 4. Risikobewertung

| Risiko | Wahrscheinlichkeit | Impact | Mitigation |
|--------|-------------------|---------|------------|
| Browser-Cache-Persistence | Hoch | Mittel | Clear-Cache-Anweisung |
| Nginx-Config-Fehler | Niedrig | Hoch | Sorgfältiges Testing |
| Asset-Hash-Kollision | Sehr niedrig | Niedrig | Streamlit-Versionierung |
| Container-Downtime | Niedrig | Mittel | Rolling-Restart |

## 5. Monitoring & Validierung

### Success Metrics
- ✅ Keine `TypeError: Failed to fetch` im Browser-Console
- ✅ Korrekte Content-Type Header für JS-Assets (`application/javascript`)
- ✅ HTTP 404 statt HTML-Fallback für nicht-existierende Assets
- ✅ Browser-Performance ohne Cache-Clear

### Monitoring Commands
```bash
# Asset-Verfügbarkeit prüfen
curl -I https://gymalf-gustav.duckdns.org/static/js/index.CD8HuT3N.js

# Nginx-Logs für Asset-Requests
docker exec gustav_nginx tail -f /var/log/nginx/access.log | grep "static/js"

# Container-Health überprüfen  
docker compose ps app
```

---

**Nächste Schritte:**
1. Sofortiger Container-Restart
2. Nginx-Konfiguration anpassen und testen
3. Long-term Asset-Monitoring Setup

**Verantwortlich:** Claude & Felix  
**Review:** Nach Implementierung Phase 2