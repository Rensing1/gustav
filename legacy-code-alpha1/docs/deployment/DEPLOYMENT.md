# GUSTAV HTTPS Deployment Guide

Dieses Dokument beschreibt, wie GUSTAV mit HTTPS über das Internet bereitgestellt wird.

## Voraussetzungen

- Domain-Name, der auf deinen Server zeigt
- Docker und Docker Compose installiert
- Ports 80 und 443 auf dem Server geöffnet
- E-Mail-Adresse für Let's Encrypt Benachrichtigungen

## Deployment-Schritte

### 1. Umgebungsvariablen konfigurieren

Kopiere `.env.example` nach `.env` und ergänze die HTTPS-spezifischen Variablen:

```bash
cp .env.example .env
```

Wichtige Variablen für HTTPS:
- `DOMAIN_NAME`: Deine Domain (z.B. `gustav.example.com`)
- `LETSENCRYPT_EMAIL`: Deine E-Mail für SSL-Benachrichtigungen
- `LETSENCRYPT_STAGING`: Auf `1` für Tests, `0` für Produktion

### 2. Entwicklungs- vs. Produktionsmodus

Die `docker-compose.yml` unterstützt beide Modi:

**Entwicklung (lokal):**
```bash
# Kommentiere die expose-Zeilen aus und aktiviere ports
# In docker-compose.yml für app und ollama:
ports:
  - "8501:8501"  # statt expose

# Starte ohne nginx/certbot
docker-compose up app ollama
```

**Produktion (HTTPS):**
```bash
# Nutze die Konfiguration wie sie ist (mit expose statt ports)
# Alle Services starten
docker-compose up -d
```

### 3. SSL-Zertifikate initialisieren

Beim ersten Deployment:

```bash
# Macht das Script ausführbar
chmod +x init-letsencrypt.sh

# Führe die Initialisierung aus
./init-letsencrypt.sh
```

Das Script:
- Erstellt temporäre Zertifikate für den nginx-Start
- Fordert echte Let's Encrypt Zertifikate an
- Konfiguriert automatische Erneuerung

### 4. Services starten

```bash
# Alle Services starten
docker-compose up -d

# Logs prüfen
docker-compose logs -f nginx
docker-compose logs -f app
```

### 5. Verbindung testen

1. Öffne https://deine-domain.com
2. Prüfe SSL-Zertifikat im Browser
3. Teste auf https://www.ssllabs.com/ssltest/

## Wartung

### Zertifikat-Erneuerung
Die Zertifikate erneuern sich automatisch. Der certbot-Container prüft alle 12 Stunden.

### Logs prüfen
```bash
# nginx Logs
docker-compose logs nginx

# Certbot Logs
docker-compose logs certbot

# App Logs
docker-compose logs app
```

### Services neustarten
```bash
# Einzelnen Service
docker-compose restart nginx

# Alle Services
docker-compose restart
```

## Sicherheitshinweise

1. **Firewall**: Nur Ports 80, 443 und SSH (falls benötigt) öffnen
2. **Updates**: Regelmäßig Docker Images aktualisieren
3. **Monitoring**: Logs und SSL-Ablaufdaten überwachen
4. **Backups**: Certbot-Zertifikate sichern (`./certbot/conf/`)
5. **Brute-Force-Schutz**: fail2ban installieren und aktivieren

### fail2ban einrichten (empfohlen)

Schützt vor Brute-Force-Angriffen auf nginx/HTTPS:

```bash
# Installation
sudo apt install fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Konfiguration für nginx erstellen
sudo nano /etc/fail2ban/jail.local
```

Inhalt für jail.local:
```ini
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5

[nginx-http-auth]
enabled = true
filter = nginx-http-auth
port = http,https
logpath = /var/log/nginx/error.log

[nginx-noscript]
enabled = true
port = http,https
filter = nginx-noscript
logpath = /var/log/nginx/access.log
maxretry = 6

[nginx-badbots]
enabled = true
port = http,https
filter = nginx-badbots
logpath = /var/log/nginx/access.log
maxretry = 2

[nginx-noproxy]
enabled = true
port = http,https
filter = nginx-noproxy
logpath = /var/log/nginx/access.log
maxretry = 2
```

Nach der Konfiguration:
```bash
sudo systemctl restart fail2ban
sudo fail2ban-client status
```

## Troubleshooting

### nginx startet nicht
- Prüfe ob Ports 80/443 frei sind
- Prüfe nginx Konfiguration: `docker-compose exec nginx nginx -t`

### Zertifikat-Fehler
- Prüfe DNS: `nslookup deine-domain.com`
- Teste mit Staging-Zertifikaten: `LETSENCRYPT_STAGING=1`
- Prüfe Rate Limits: https://letsencrypt.org/docs/rate-limits/

### Streamlit nicht erreichbar
- Container läuft: `docker-compose ps`
- Interne Verbindung: `docker-compose exec nginx curl http://app:8501`

## Architektur

```
Internet
    ↓ (HTTPS:443)
  nginx 
    ↓ (HTTP:8501)
Streamlit App
    ↓ (HTTP:11434)      ↓ (HTTP:54321)
  Ollama              Supabase
  (intern)            (host.docker.internal)
```

Nur nginx ist von außen erreichbar. Alle anderen Services sind intern.